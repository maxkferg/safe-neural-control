import React, { useState } from "react";
import {
  Table,
  TableRow,
  TableHead,
  TableBody,
  TableCell,
  Menu,
  MenuItem,
  Typography,
  IconButton
} from "@material-ui/core";
// components
import { Button } from "../../../../components/Wrappers";
import { deleteBuilding as deleteBuildingGraphql } from '../../../../services/BuildingServices';

import { MoreVert as MoreIcon } from "@material-ui/icons";
const tableHeader = ['name', 'owner', 'status', 'action']

function handleClickBuilding(event, buildingId, history) {
  event.stopPropagation()
  history.push(`/app/building/${buildingId}/model`)
}

export default function TableComponent({ buildings, classes, history, setIsFetchBuildings, isFetchBuildings }) {
  const [isMoreMenuOpen, setMoreMenuOpen] = useState(false);
  const [moreButtonRef, setMoreButtonRef] = useState(null);
  const [currentBuilding, setCurrentBuilding] = useState(null);
  const keys = tableHeader.map(i => i.toUpperCase());
  console.log('akakak', buildings)
  async function deleteBuilding(buildingId) {
    await deleteBuildingGraphql({ buildingId });
    setIsFetchBuildings(!isFetchBuildings);
  }
  return (
    <div>
    <Table className="mb-0">
      <TableHead>
        <TableRow>
          {keys.map(key => (
            <TableCell key={key}>{key}</TableCell>
          ))}
        </TableRow>
      </TableHead>
      <TableBody>
        {buildings.map(({ id, name, owner_id, isDeleted }) => (
            <TableRow onClick={(e) => handleClickBuilding(e, id, history)} key={id}>
            <TableCell className="pl-3 fw-normal">{name}</TableCell>
            <TableCell>{owner_id}</TableCell>
            <TableCell>
              <Button
                onClick={e => e.stopPropagation()}
                color={isDeleted ? 'error' : 'success'}
                size="small"
                className="px-2"
                variant="contained"
              >
                {isDeleted ? 'Deleted' : 'Active'}
              </Button>
            </TableCell>
            <TableCell>
              <IconButton
                color="primary"
                aria-owns="widget-menu"
                aria-haspopup="true"
                classes={{ root: classes.moreButton }}
                onClick={(e) => {
                  e.stopPropagation();
                  setCurrentBuilding(id)
                  setMoreMenuOpen(true)
                  setMoreButtonRef(e.target)
                }}
                buttonRef={setMoreButtonRef}
              >
                <MoreIcon />
              </IconButton>
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
      <Menu
          id="widget-menu"
          open={isMoreMenuOpen}
          anchorEl={moreButtonRef}
          onClose={() => setMoreMenuOpen(false)}
          disableAutoFocusItem
          >
          <MenuItem onClick={e => {
              deleteBuilding(currentBuilding)
              setMoreMenuOpen(false)
            }}>
            <Typography>Delete</Typography>
          </MenuItem>
        </Menu>
    </Table>
    </div>
  );
}
