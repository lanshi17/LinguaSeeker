import { wsService } from '../services/websocket';

import { createWorkflowStore } from './workflowStore';

export const useWorkflowStore = createWorkflowStore(wsService);
