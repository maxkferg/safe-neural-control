from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

from gym.spaces import Box
import numpy as np
import logging

import ray
import ray.experimental.tf_utils
from ray.rllib.agents.ddpg.noop_model import NoopModel
from ray.rllib.agents.dqn.dqn_policy import _postprocess_dqn, PRIO_WEIGHTS
from ray.rllib.policy.sample_batch import SampleBatch
from ray.rllib.policy.tf_policy import TFPolicy
from ray.rllib.policy.tf_policy_template import build_tf_policy
from ray.rllib.models import ModelCatalog
from ray.rllib.utils.error import UnsupportedSpaceException
from ray.rllib.utils import try_import_tf, try_import_tfp
from ray.rllib.utils.annotations import override
from ray.rllib.utils.tf_ops import minimize_and_clip, make_tf_callable
from .sacq_model import SACQModel

tf = try_import_tf()
tfp = try_import_tfp()
logger = logging.getLogger(__name__)


def build_sac_model(policy, obs_space, action_space, config):
    if config["model"]["custom_model"]:
        logger.warning(
            "Setting use_state_preprocessor=True since a custom model "
            "was specified.")
        config["use_state_preprocessor"] = True
    if not isinstance(action_space, Box):
        raise UnsupportedSpaceException(
            "Action space {} is not supported for SAC.".format(action_space))
    if len(action_space.shape) > 1:
        raise UnsupportedSpaceException(
            "Action space has multiple dimensions "
            "{}. ".format(action_space.shape) +
            "Consider reshaping this into a single dimension, "
            "using a Tuple action space, or the multi-agent API.")

    if config["use_state_preprocessor"]:
        default_model = None  # catalog decides
        num_outputs = 256  # arbitrary
        config["model"]["no_final_linear"] = True
    else:
        default_model = NoopModel
        num_outputs = int(np.product(obs_space.shape))

    policy.model = ModelCatalog.get_model_v2(
        obs_space,
        action_space,
        num_outputs,
        config["model"],
        framework="tf",
        model_interface=SACQModel,
        default_model=default_model,
        name="sac_model",
        actor_hidden_activation=config["policy_model"]["hidden_activation"],
        actor_hiddens=config["policy_model"]["hidden_layer_sizes"],
        critic_hidden_activation=config["Q_model"]["hidden_activation"],
        critic_hiddens=config["Q_model"]["hidden_layer_sizes"],
        twin_q=config["twin_q"])

    policy.target_model = ModelCatalog.get_model_v2(
        obs_space,
        action_space,
        num_outputs,
        config["model"],
        framework="tf",
        model_interface=SACQModel,
        default_model=default_model,
        name="target_sac_model",
        actor_hidden_activation=config["policy_model"]["hidden_activation"],
        actor_hiddens=config["policy_model"]["hidden_layer_sizes"],
        critic_hidden_activation=config["Q_model"]["hidden_activation"],
        critic_hiddens=config["Q_model"]["hidden_layer_sizes"],
        twin_q=config["twin_q"])

    return policy.model


def postprocess_trajectory(policy,
                           sample_batch,
                           other_agent_batches=None,
                           episode=None):
    return _postprocess_dqn(policy, sample_batch)


def build_action_output(policy, model, input_dict, obs_space, action_space,
                        config):
    model_out, _ = model({
        "obs": input_dict[SampleBatch.CUR_OBS],
        "is_training": policy._get_is_training_placeholder(),
    }, [], None)

    def unsquash_actions(actions):
        # Use sigmoid to scale to [0,1], but also double magnitude of input to
        # emulate behaviour of tanh activation used in SAC and TD3 papers.
        sigmoid_out = tf.nn.sigmoid(2 * actions)
        # Rescale to actual env policy scale
        # (shape of sigmoid_out is [batch_size, dim_actions], so we reshape to
        # get same dims)
        action_range = (action_space.high - action_space.low)[None]
        low_action = action_space.low[None]
        unsquashed_actions = action_range * sigmoid_out + low_action

        return unsquashed_actions

    squashed_stochastic_actions, log_pis = policy.model.get_policy_output(
        model_out, deterministic=False)
    stochastic_actions = unsquash_actions(squashed_stochastic_actions)
    squashed_deterministic_actions, _ = policy.model.get_policy_output(
        model_out, deterministic=True)
    deterministic_actions = unsquash_actions(squashed_deterministic_actions)

    actions = tf.cond(policy.stochastic, lambda: stochastic_actions,
                      lambda: deterministic_actions)

    action_probabilities = tf.cond(policy.stochastic, lambda: log_pis,
                                   lambda: tf.zeros_like(log_pis))
    policy.output_actions = actions
    return actions, action_probabilities


def actor_critic_loss(policy, model, _, train_batch):
    model_out_t, _ = model({
        "obs": train_batch[SampleBatch.CUR_OBS],
        "is_training": policy._get_is_training_placeholder(),
    }, [], None)

    model_out_tp1, _ = model({
        "obs": train_batch[SampleBatch.NEXT_OBS],
        "is_training": policy._get_is_training_placeholder(),
    }, [], None)

    target_model_out_tp1, _ = policy.target_model({
        "obs": train_batch[SampleBatch.NEXT_OBS],
        "is_training": policy._get_is_training_placeholder(),
    }, [], None)
    # TODO(hartikainen): figure actions and log pis
    policy_t, log_pis_t = model.get_policy_output(model_out_t)
    policy_tp1, log_pis_tp1 = model.get_policy_output(model_out_tp1)

    log_alpha = model.log_alpha
    alpha = model.alpha

    # q network evaluation
    q_t = model.get_q_values(model_out_t, train_batch[SampleBatch.ACTIONS])
    if policy.config["twin_q"]:
        twin_q_t = model.get_twin_q_values(model_out_t,
                                           train_batch[SampleBatch.ACTIONS])

    # Q-values for current policy (no noise) in given current state
    q_t_det_policy = model.get_q_values(model_out_t, policy_t)

    # target q network evaluation
    q_tp1 = policy.target_model.get_q_values(target_model_out_tp1, policy_tp1)
    
    # CUSTOM:
    # Clip the target Q prediction
    print("Clipping Q function to [-4,4]")
    q_tp1 = tf.clip_by_value(q_tp1, -4, 4)

    if policy.config["twin_q"]:
        twin_q_tp1 = policy.target_model.get_twin_q_values(
            target_model_out_tp1, policy_tp1)
    
    q_t_selected = tf.squeeze(q_t, axis=len(q_t.shape) - 1)
    if policy.config["twin_q"]:
        twin_q_t_selected = tf.squeeze(twin_q_t, axis=len(q_t.shape) - 1)
        q_tp1 = tf.minimum(q_tp1, twin_q_tp1)

    q_tp1 -= tf.expand_dims(alpha * log_pis_t, 1)

    q_tp1_best = tf.squeeze(input=q_tp1, axis=len(q_tp1.shape) - 1)
    q_tp1_best_masked = (
        1.0 - tf.cast(train_batch[SampleBatch.DONES], tf.float32)) * q_tp1_best

    assert policy.config["n_step"] == 1, "TODO(hartikainen) n_step > 1"

    # compute RHS of bellman equation
    q_t_selected_target = tf.stop_gradient(
        train_batch[SampleBatch.REWARDS] +
        policy.config["gamma"]**policy.config["n_step"] * q_tp1_best_masked)

    # compute the error (potentially clipped)
    if policy.config["twin_q"]:
        td_error = q_t_selected - q_t_selected_target
        twin_td_error = twin_q_t_selected - q_t_selected_target
        td_error = td_error + twin_td_error
        errors = 0.5 * (tf.square(td_error) + tf.square(twin_td_error))
    else:
        td_error = q_t_selected - q_t_selected_target
        errors = 0.5 * tf.square(td_error)

    critic_loss = model.custom_loss(
        tf.reduce_mean(train_batch[PRIO_WEIGHTS] * errors), train_batch)
    actor_loss = tf.reduce_mean(alpha * log_pis_t - q_t_det_policy)

    target_entropy = (-np.prod(policy.action_space.shape)
                      if policy.config["target_entropy"] == "auto" else
                      policy.config["target_entropy"])
    alpha_loss = -tf.reduce_mean(
        log_alpha * tf.stop_gradient(log_pis_t + target_entropy))

    # save for stats function
    policy.q_t = q_t
    policy.td_error = td_error
    policy.actor_loss = actor_loss
    policy.critic_loss = critic_loss
    policy.alpha_loss = alpha_loss

    # in a custom apply op we handle the losses separately, but return them
    # combined in one loss for now
    return actor_loss + critic_loss + alpha_loss


def gradients(policy, optimizer, loss):
    if policy.config["grad_norm_clipping"] is not None:
        actor_grads_and_vars = minimize_and_clip(
            optimizer,
            policy.actor_loss,
            var_list=policy.model.policy_variables(),
            clip_val=policy.config["grad_norm_clipping"])
        critic_grads_and_vars = minimize_and_clip(
            optimizer,
            policy.critic_loss,
            var_list=policy.model.q_variables(),
            clip_val=policy.config["grad_norm_clipping"])
        alpha_grads_and_vars = minimize_and_clip(
            optimizer,
            policy.alpha_loss,
            var_list=[policy.model.log_alpha],
            clip_val=policy.config["grad_norm_clipping"])
    else:
        actor_grads_and_vars = optimizer.compute_gradients(
            policy.actor_loss, var_list=policy.model.policy_variables())
        critic_grads_and_vars = optimizer.compute_gradients(
            policy.critic_loss, var_list=policy.model.q_variables())
        alpha_grads_and_vars = optimizer.compute_gradients(
            policy.alpha_loss, var_list=[policy.model.log_alpha])
    # save these for later use in build_apply_op
    policy._actor_grads_and_vars = [(g, v) for (g, v) in actor_grads_and_vars
                                    if g is not None]
    policy._critic_grads_and_vars = [(g, v) for (g, v) in critic_grads_and_vars
                                     if g is not None]
    policy._alpha_grads_and_vars = [(g, v) for (g, v) in alpha_grads_and_vars
                                    if g is not None]
    grads_and_vars = (
        policy._actor_grads_and_vars + policy._critic_grads_and_vars +
        policy._alpha_grads_and_vars)
    return grads_and_vars


def stats(policy, train_batch):
    return {
        "td_error": tf.reduce_mean(policy.td_error),
        "actor_loss": tf.reduce_mean(policy.actor_loss),
        "critic_loss": tf.reduce_mean(policy.critic_loss),
        "mean_q": tf.reduce_mean(policy.q_t),
        "max_q": tf.reduce_max(policy.q_t),
        "min_q": tf.reduce_min(policy.q_t),
    }


class ExplorationStateMixin(object):
    def __init__(self, obs_space, action_space, config):
        self.stochastic = tf.get_variable(
            initializer=tf.constant_initializer(config["exploration_enabled"]),
            name="stochastic",
            shape=(),
            trainable=False,
            dtype=tf.bool)

    def set_epsilon(self, epsilon):
        pass


class ActorCriticOptimizerMixin(object):
    def __init__(self, config):
        # create global step for counting the number of update operations
        self.global_step = tf.train.get_or_create_global_step()

        # use separate optimizers for actor & critic
        self._actor_optimizer = tf.train.AdamOptimizer(
            learning_rate=config["optimization"]["actor_learning_rate"])
        self._critic_optimizer = tf.train.AdamOptimizer(
            learning_rate=config["optimization"]["critic_learning_rate"])
        self._alpha_optimizer = tf.train.AdamOptimizer(
            learning_rate=config["optimization"]["entropy_learning_rate"])


class ComputeTDErrorMixin(object):
    def __init__(self):
        @make_tf_callable(self.get_session(), dynamic_shape=True)
        def compute_td_error(obs_t, act_t, rew_t, obs_tp1, done_mask,
                             importance_weights):
            # Do forward pass on loss to update td error attribute
            actor_critic_loss(
                self, self.model, None, {
                    SampleBatch.CUR_OBS: tf.convert_to_tensor(obs_t),
                    SampleBatch.ACTIONS: tf.convert_to_tensor(act_t),
                    SampleBatch.REWARDS: tf.convert_to_tensor(rew_t),
                    SampleBatch.NEXT_OBS: tf.convert_to_tensor(obs_tp1),
                    SampleBatch.DONES: tf.convert_to_tensor(done_mask),
                    PRIO_WEIGHTS: tf.convert_to_tensor(importance_weights),
                })

            return self.td_error

        self.compute_td_error = compute_td_error


class TargetNetworkMixin(object):
    def __init__(self, config):
        @make_tf_callable(self.get_session())
        def update_target_fn(tau):
            tau = tf.convert_to_tensor(tau, dtype=tf.float32)
            update_target_expr = []
            model_vars = self.model.trainable_variables()
            target_model_vars = self.target_model.trainable_variables()
            assert len(model_vars) == len(target_model_vars), \
                (model_vars, target_model_vars)
            for var, var_target in zip(model_vars, target_model_vars):
                update_target_expr.append(
                    var_target.assign(tau * var + (1.0 - tau) * var_target))
                logger.debug("Update target op {}".format(var_target))
            return tf.group(*update_target_expr)

        # Hard initial update
        self._do_update = update_target_fn
        self.update_target(tau=1.0)

    # support both hard and soft sync
    def update_target(self, tau=None):
        self._do_update(np.float32(tau or self.config.get("tau")))

    @override(TFPolicy)
    def variables(self):
        return self.model.variables() + self.target_model.variables()


def setup_early_mixins(policy, obs_space, action_space, config):
    ExplorationStateMixin.__init__(policy, obs_space, action_space, config)
    ActorCriticOptimizerMixin.__init__(policy, config)


def setup_mid_mixins(policy, obs_space, action_space, config):
    ComputeTDErrorMixin.__init__(policy)


def setup_late_mixins(policy, obs_space, action_space, config):
    TargetNetworkMixin.__init__(policy, config)


SACQTFPolicy = build_tf_policy(
    name="SACQTFPolicy",
    get_default_config=lambda: ray.rllib.agents.sac.sac.DEFAULT_CONFIG,
    make_model=build_sac_model,
    postprocess_fn=postprocess_trajectory,
    action_sampler_fn=build_action_output,
    loss_fn=actor_critic_loss,
    stats_fn=stats,
    gradients_fn=gradients,
    extra_learn_fetches_fn=lambda policy: {"td_error": policy.td_error},
    mixins=[
        TargetNetworkMixin, ExplorationStateMixin, ActorCriticOptimizerMixin,
        ComputeTDErrorMixin
    ],
    before_init=setup_early_mixins,
    before_loss_init=setup_mid_mixins,
    after_init=setup_late_mixins,
    obs_include_prev_action_reward=False)