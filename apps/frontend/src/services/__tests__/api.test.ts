import { describe, it, expect } from 'vitest';
import { uploadTaskRequest } from '../api';

describe('api', () => {
  it('should compile uploadTaskRequest correctly', () => {
    expect(typeof uploadTaskRequest).toBe('function');
  });
});
