import { describe, it, expect } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { useTaskFlowStore } from '../useTaskFlowStore';

describe('useTaskFlowStore', () => {
  it('should store and update confirmed request id', () => {
    const { result } = renderHook(() => useTaskFlowStore());
    
    expect(result.current.confirmedRequestId).toBe(null);
    
    act(() => {
      result.current.setConfirmedRequestId('req-123');
    });
    
    expect(result.current.confirmedRequestId).toBe('req-123');
  });

  it('should store and update task form payload', () => {
    const { result } = renderHook(() => useTaskFlowStore());
    
    expect(result.current.taskFormPayload).toBe(null);
    
    act(() => {
      result.current.setTaskFormPayload({ foo: 'bar' });
    });
    
    expect(result.current.taskFormPayload).toEqual({ foo: 'bar' });
  });
});
