/**
 * 任务管理 Hook
 */
import { useState, useCallback, useEffect } from 'react';
import type { Task, TaskTypeValue, TaskStatusValue } from '../types/task';

export function useTasks() {
  const [tasks, setTasks] = useState<Task[]>(() => {
    // 从 localStorage 恢复
    if (typeof window !== 'undefined') {
      const saved = localStorage.getItem('multi-acmg-tasks');
      if (saved) {
        try {
          return JSON.parse(saved);
        } catch {
          return [];
        }
      }
    }
    return [];
  });

  // 持久化到 localStorage
  useEffect(() => {
    localStorage.setItem('multi-acmg-tasks', JSON.stringify(tasks));
  }, [tasks]);

  // 创建任务
  const createTask = useCallback((type: TaskTypeValue, title: string, description?: string): Task => {
    const task: Task = {
      id: `task-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`,
      type,
      status: 'pending' as TaskStatusValue,
      title,
      description,
      progress: 0,
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
    };
    setTasks(prev => [task, ...prev]);
    return task;
  }, []);

  // 更新任务状态
  const updateTask = useCallback((taskId: string, updates: Partial<Task>) => {
    setTasks(prev => prev.map(task => 
      task.id === taskId 
        ? { ...task, ...updates, updatedAt: new Date().toISOString() }
        : task
    ));
  }, []);

  // 开始处理任务
  const startTask = useCallback((taskId: string) => {
    updateTask(taskId, { status: 'processing', progress: 0 });
  }, [updateTask]);

  // 更新进度
  const updateProgress = useCallback((taskId: string, progress: number) => {
    updateTask(taskId, { progress });
  }, [updateTask]);

  // 完成任务
  const completeTask = useCallback((taskId: string, result?: Task['result']) => {
    updateTask(taskId, { status: 'completed', progress: 100, result });
  }, [updateTask]);

  // 任务失败
  const failTask = useCallback((taskId: string, error: string) => {
    updateTask(taskId, { status: 'failed', error });
  }, [updateTask]);

  // 删除任务
  const removeTask = useCallback((taskId: string) => {
    setTasks(prev => prev.filter(t => t.id !== taskId));
  }, []);

  // 清空已完成任务
  const clearCompleted = useCallback(() => {
    setTasks(prev => prev.filter(t => t.status !== 'completed'));
  }, []);

  // 获取活跃任务数
  const activeCount = tasks.filter(t => t.status === 'pending' || t.status === 'processing').length;
  const completedCount = tasks.filter(t => t.status === 'completed').length;

  return {
    tasks,
    activeCount,
    completedCount,
    createTask,
    updateTask,
    startTask,
    updateProgress,
    completeTask,
    failTask,
    removeTask,
    clearCompleted,
  };
}
