import { RouterProvider } from 'react-router-dom';

import { NotificationToast } from './components/feedback/notification-toast';
import { router } from './router';

const App: React.FC = () => {
  return (
    <>
      <RouterProvider router={router} />
      <NotificationToast />
    </>
  );
};

export default App;
