import React, { useState } from 'react';
import { connect } from 'react-redux';
import Avatar from '@material-ui/core/Avatar';
import Button from '@material-ui/core/Button';
import CssBaseline from '@material-ui/core/CssBaseline';
import TextField from '@material-ui/core/TextField';
import { Link } from 'react-router-dom';
import Grid from '@material-ui/core/Grid';
import LockOutlinedIcon from '@material-ui/icons/LockOutlined';
import Typography from '@material-ui/core/Typography';
import { makeStyles } from '@material-ui/core/styles';
import Container from '@material-ui/core/Container';
import { signUp } from '../../services/AuthServices';
import validateSignUp from './validateSignUp';
import { showError } from '../../redux/actions/showAlert'

const useStyles = makeStyles(theme => ({
  '@global': {
    body: {
      backgroundColor: theme.palette.common.white,
    },
  },
  paper: {
    marginTop: theme.spacing(8),
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
  },
  avatar: {
    margin: theme.spacing(1),
    backgroundColor: theme.palette.secondary.main,
  },
  form: {
    width: '100%', // Fix IE 11 issue.
    marginTop: theme.spacing(3),
  },
  submit: {
    margin: theme.spacing(3, 0, 2),
  },
}));

function SignUp(props) {
  const classes = useStyles();
  const [email, setEmail] = useState();
  const [password, setPassword] = useState();
  const [firstName, setFirstName] = useState();
  const [lastName, setLastName] = useState();
  const [validation, setValidation] = useState();

  const checkPayload = payload => {
    const signUpPayload = {
      email: payload.email || email,
      password: payload.password || password,
      firstName: payload.firstName || firstName,
      lastName: payload.lastName || lastName
    }
    if (!!validation) {
      const check = validateSignUp(signUpPayload);
      setValidation(check);
      return check
    }
    return
  }

  const submitSignIn = async () => {
    // should add check 
    const signUpPayload = {
      email,
      password,
      firstName,
      lastName
    }

    const check = validateSignUp(signUpPayload);
    setValidation(check);

    if (check.valid) {
      const response = await signUp(signUpPayload);
      const isError = response instanceof Error;
      if (isError) {
        props.showError(response.message.replace('GraphQL error: Error: ', ''))
      } else {
        const { data } = response
        if (data.createUser.authToken) {
          localStorage.setItem('token', data.createUser.authToken);
          props.history.push('/123132/model');
        }
      }
    }
  }

  return (
    <Container component="main" maxWidth="xs">
      <CssBaseline />
      <div className={classes.paper}>
        <Avatar className={classes.avatar}>
          <LockOutlinedIcon />
        </Avatar>
        <Typography component="h1" variant="h5">
          Sign up
        </Typography>
        <Grid container spacing={2}>
          <Grid item xs={12} sm={6}>
            <TextField
              autoComplete="fname"
              name="firstName"
              variant="outlined"
              required
              fullWidth
              id="firstName"
              label="First Name"
              autoFocus
              onChange={e => {
                checkPayload({ firstName: e.target.value })
                setFirstName(e.target.value)
              }}
              error={!!validation && !!validation.firstNameMessage}
              helperText={!!validation && validation.firstNameMessage}
            />
          </Grid>
          <Grid item xs={12} sm={6}>
            <TextField
              variant="outlined"
              required
              fullWidth
              id="lastName"
              label="Last Name"
              name="lastName"
              autoComplete="lname"
              onChange={e => {
                checkPayload({ lastName: e.target.value })
                setLastName(e.target.value)
              }}
              error={!!validation && !!validation.lastNameMessage}
              helperText={!!validation && validation.lastNameMessage}
            />
          </Grid>
          <Grid item xs={12}>
            <TextField
              variant="outlined"
              required
              fullWidth
              id="email"
              label="Email Address"
              name="email"
              autoComplete="email"
              onChange={e => {
                checkPayload({ email: e.target.value })
                setEmail(e.target.value)
              }}
              error={!!validation && !!validation.emailMessage}
              helperText={!!validation && validation.emailMessage}
            />
          </Grid>
          <Grid item xs={12}>
            <TextField
              variant="outlined"
              required
              fullWidth
              name="password"
              label="Password"
              type="password"
              id="password"
              autoComplete="current-password"
              onChange={e => {
                checkPayload({ password: e.target.value })
                setPassword(e.target.value)
              }}
              error={!!validation && !!validation.passwordMessage}
              helperText={!!validation && validation.passwordMessage}
            />
          </Grid>
        </Grid>
        <Button
          type="submit"
          fullWidth
          variant="contained"
          color="primary"
          className={classes.submit}
          onClick={submitSignIn}
        >
          Sign Up
          </Button>
        <Grid container justify="flex-end">
          <Grid item>
            <Link to="/sign-in">
              <div>
                Already have an account? Sign in
                </div>
            </Link>
          </Grid>
        </Grid>
      </div>
    </Container>
  );
}

const mapDispatchToProps = dispatch => ({
  showError: message =>
    dispatch(showError(message))
})

export default connect(null, mapDispatchToProps)(SignUp)