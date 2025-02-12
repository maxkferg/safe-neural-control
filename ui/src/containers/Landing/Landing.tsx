import React from 'react';
import { Redirect } from 'react-router-dom'
import CssBaseline from '@material-ui/core/CssBaseline';
import { makeStyles } from '@material-ui/core/styles';
import LandingHeader from '../../components/LandingHeader';
import LandingContent from '../../components/LandingContent';

const useStyles = makeStyles(theme => ({
  'html,body': {
    height: '100%',
    margin: 0,
  },
  LandingHeaderContainer: {
    background: "linear-gradient(to right bottom, #131c47, #192152, #474c9a, #ac93d2)",
    height: '971px',
    overflow: 'hidden'
  }
}));

export default function Pricing(props) {
  const classes = useStyles();
  if (!localStorage.getItem('token')) {
    return (
      <React.Fragment>
        <CssBaseline />
        <div className={classes.LandingHeaderContainer}>
          <LandingHeader />
          <LandingContent />
        </div>
      </React.Fragment>
    );
  }
  return <Redirect to='/app/buildings' />
}