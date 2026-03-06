import { create } from 'zustand';
import type { StateCreator } from 'zustand';
import { devtools } from 'zustand/middleware';
import { createTaskSlice } from './taskStore';
import type { TaskSlice } from './taskStore/types';
import { createUISlice } from './uiStore';
import type { UISlice } from './uiStore';
import { createNotificationSlice } from './notificationStore';
import type { NotificationSlice } from './notificationStore';

type AppStore = TaskSlice & UISlice & NotificationSlice;

const createAppSlice: StateCreator<AppStore> = (...a) => ({
  ...createTaskSlice(...a),
  ...createUISlice(...a),
  ...createNotificationSlice(...a),
});

export const useAppStore = create(
  devtools(createAppSlice, { name: 'MultiACMG-Store' })
);