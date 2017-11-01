import React from 'react';

import { Admin, Resource } from 'admin-on-rest';

import UserIcon from 'material-ui/svg-icons/hardware/developer-board';

import { Delete } from 'admin-on-rest/lib/mui';

import { UserList, UserCreate, UserEdit } from './views/User';

import restClient from './restClient';
import authClient from './authClient';

const App = () => (
  <Admin title="microauth" authClient={authClient} restClient={restClient}>
    <Resource name="users" list={UserList} create={UserCreate} edit={UserEdit} remove={Delete} icon={UserIcon} />
  </Admin>
);

export default App;
