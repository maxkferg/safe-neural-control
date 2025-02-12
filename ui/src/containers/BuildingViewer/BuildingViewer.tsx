/**
 * Renders the Babylon viewer with state frmo the database
 */
import * as React from 'react';
import BabylonViewer from '../BabylonViewer/BabylonViewer';
import { withStyles, WithStyles, Theme } from '@material-ui/core/styles';
import apollo from '../../apollo';
import { withRouter } from 'react-router-dom';
import SubscriptionClient from '../../apollo/websocket';
import { loader } from 'graphql.macro';
import { difference } from 'lodash';
import { connect } from 'react-redux';

const BUFFER_POINT = 10000;
const GET_MESH_BUILDING_QUERY = loader('../../graphql/getMeshesBuilding.gql');
const SUBSCRIBE_MESH_POSITION = loader('../../graphql/subscribeMesh.gql');
const POLL_INTERVAL = 5000 // 5 seconds
const POLL_INTERVAL_BOT_POSITION = 100
const SUB_POINTS_ROBOT = loader('../../graphql/subscribePointsOfRobot.gql');
const styles = (theme: Theme) => ({
  fab: {
    margin: theme.spacing(),
    position: "absolute",
    bottom: 30 + "px",
    right: 30 + "px",
  },
});

//@ts-ignore
export interface Props extends WithStyles<typeof styles>{
  onSelectedObject: Function
  match: any
  pointCloudLimit: any
  history: any
  pointCloudStrategy: any
  subscribePointCloud: boolean
}

interface State {
  error: boolean,
  loading: boolean,
  meshesCurrent: any,
  deleteMesh: any[],
  points: any[],
  marker: boolean
}



class BuildingViewer extends React.Component<Props, State> {
    classes: any
    subScription: any
    subPointCloud: any
    subscriptionPointCloud: {}
    prevPoints: any[]

    constructor(props: any) {
      super(props);
      this.state = {
        error: false,
        loading: true,
        meshesCurrent: [],
        deleteMesh: [],
        points: [],
        marker: false,
      };
      this.prevPoints = [];
      this.subscriptionPointCloud = {};
      this.classes = props.classes;
    }

    async componentDidMount(){
      let self = this;
      this.subScription = apollo.watchQuery({
        query: GET_MESH_BUILDING_QUERY,
        pollInterval: POLL_INTERVAL,
        variables : { buildingId: this.props.match.params.buildingId }}
      ).subscribe(data => {
        let meshesCurrent = data.data.meshesOfBuilding;
        const meshIdsFromAPI = meshesCurrent.map(el => el.id);
        const meshIdsFromState = this.state.meshesCurrent.map(el => el.id);
        const deleteMesh = difference(meshIdsFromState, meshIdsFromAPI);
        this.setState({
          loading: false,
          meshesCurrent,
          deleteMesh,
          marker: !this.state.marker
        });
      })
     }

    componentDidUpdate(prevProps, prevState) {
      const { subscribePointCloud, pointCloudStrategy } = this.props;
      const { meshesCurrent } = this.state;
      let self = this;
      if (prevState.meshesCurrent.length !== meshesCurrent.length) {
        // Subscribe to changes in robot/mesh position
        for (let i=0; i < meshesCurrent.length; i++) {
          if (meshesCurrent[i].type === 'robot') {
            // Subscribe to changes in robot/mesh position
            SubscriptionClient.subscribe({
              query: SUBSCRIBE_MESH_POSITION,
              variables: {
                id: meshesCurrent[i].id
              }
            }).subscribe({
              next (data) {
                for (let j=0; j<self.state.meshesCurrent.length; j++){
                  if (self.state.meshesCurrent[j].id == data.data.meshPosition.id){
                    let meshCopy = Object.assign({}, self.state.meshesCurrent[j]);
                    meshCopy.x = data.data.meshPosition.position.x
                    meshCopy.y = data.data.meshPosition.position.y
                    meshCopy.z = data.data.meshPosition.position.z
                    meshCopy.theta = data.data.meshPosition.position.theta
                    self.state.meshesCurrent[j] = meshCopy;
                    self.setState({
                      marker: !self.state.marker,
                      meshesCurrent: self.state.meshesCurrent
                    });
                  }
                }
              }
            })
          }
        }
      }

      if (this.props.history.location.pathname.includes("point-cloud")) {
        meshesCurrent.forEach(mesh => {
          if (mesh.type === 'robot') {
            if (this.subscriptionPointCloud[mesh.id]) {
              if (!subscribePointCloud) {
                this.subscriptionPointCloud[mesh.id].unsubscribe()
                this.subscriptionPointCloud[mesh.id] = null
              } else if (pointCloudStrategy !== prevProps.pointCloudStrategy) {
                this.subscriptionPointCloud[mesh.id].unsubscribe()
                this.subscriptionPointCloud[mesh.id] = null
                this.subscriptionPointCloud[mesh.id] = SubscriptionClient.subscribe({
                  query: SUB_POINTS_ROBOT,
                  variables: {
                    id: mesh.id,
                    strategy: pointCloudStrategy
                  }
                }).subscribe({
                  next(data) {
                    const { pointCloud } = data.data;
                    self.prevPoints = self.prevPoints.concat(pointCloud.pointsGroup);
                    if (self.prevPoints.length> BUFFER_POINT) {
                      self.setState({
                        points: pointCloud.pointsGroup
                      })
                      self.prevPoints = []
                    }
                  }
                })
              }
            } else {
              this.subscriptionPointCloud[mesh.id] = SubscriptionClient.subscribe({
                query: SUB_POINTS_ROBOT,
                variables: {
                  id: mesh.id,
                  strategy: pointCloudStrategy
                }
              }).subscribe({
                next(data) {
                  const { pointCloud } = data.data;
                  self.prevPoints = self.prevPoints.concat(pointCloud.pointsGroup);
                  if (self.prevPoints.length> BUFFER_POINT) {
                    self.setState({
                      points: pointCloud.pointsGroup
                    })
                    self.prevPoints = []
                  }
                }
              })
            }
          }
        })
      }

      if (this.props.match.params.buildingId !== prevProps.match.params.buildingId) {
        if (this.subScription) this.subScription.unsubscribe();
        this.subScription = apollo.watchQuery({
          query: GET_MESH_BUILDING_QUERY, 
          pollInterval: POLL_INTERVAL, 
          variables : { buildingId: this.props.match.params.buildingId }}
        ).subscribe(data => {
          let meshesCurrent = data.data.meshesOfBuilding;
          const meshIdsFromAPI = meshesCurrent.map(el => el.id);
          const meshIdsFromState = this.state.meshesCurrent.map(el => el.id);
          const deleteMesh = difference(meshIdsFromState, meshIdsFromAPI);

          this.setState({
            loading: false,
            meshesCurrent,
            deleteMesh,
            marker: !this.state.marker
          });
        })
    }

    }

    componentWillUnmount() {
      if (this.subScription) {
        this.subScription.unsubscribe();
      }
      if (Object.keys(this.subscriptionPointCloud).length) {
        for (const property in this.subscriptionPointCloud) {
          this.subscriptionPointCloud[property].unsubscribe()
        }
      }
    }

    public render() {
      // if (this.state.loading) return 'Loading...';
      if (this.state.error) return `Error! ${this.state.error}`;
      //@ts-ignore
      return <BabylonViewer marker={this.state.marker}
        points={this.state.points}
        geometry={this.state.meshesCurrent}
        deleteMesh={this.state.deleteMesh}
        onSelectedObject={this.props.onSelectedObject}
      />
    }
}

//@ts-ignore
BuildingViewer.defaultProps = {
  subscribePointCloud: true
}
const mapStateToProps = state => ({
  pointCloudLimit: state.pointCloudSetting.limit,
  pointCloudStrategy: state.pointCloudSetting.strategy,
  subscribePointCloud: state.pointCloudSetting.subscribePointCloud
})
//@ts-ignore
export default connect(mapStateToProps)(withStyles(styles)(withRouter(BuildingViewer)));