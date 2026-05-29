import asyncio
from typing import List, Dict, Any, Callable
import time

class ParallelManager:
    """
    Manages Swarm Slots and Throttling for concurrent task execution.
    """
    def __init__(self, max_slots: int = 4):
        self.semaphore = asyncio.Semaphore(max_slots)
        self.active_tasks = 0

    async def run_task(self, task_func: Callable, *args, **kwargs):
        """
        Runs a task within a controlled swarm slot.
        """
        async with self.semaphore:
            self.active_tasks += 1
            print(f"🛰️ SWARM SLOT ACQUIRED. Active: {self.active_tasks}")
            try:
                start_time = time.time()
                result = await task_func(*args, **kwargs)
                duration = time.time() - start_time
                print(f"🏁 TASK COMPLETE in {duration:.2f}s. Releasing slot.")
                return result
            finally:
                self.active_tasks -= 1

    def decompose_parallel_groups(self, tasks: List[Dict[str, Any]]) -> List[List[Dict[str, Any]]]:
        """
        Analyzes a task list and groups them into parallel-executable batches.
        Rules:
        - Research/Audit/Search tasks can run in parallel.
        - Edit/Write/Test tasks are sequential (blocking).
        """
        groups = []
        current_group = []
        
        # Parallelizable worker types or task keywords
        parallel_signals = ["research", "search", "audit", "view", "auditor"]
        
        for task in tasks:
            task_desc = task.get("task_description", "").lower()
            worker_type = task.get("worker_type", "").lower()
            
            is_parallel = any(p in task_desc for p in parallel_signals) or \
                          any(p in worker_type for p in parallel_signals)
            
            if is_parallel:
                current_group.append(task)
            else:
                # If we have a pending parallel group, flush it first
                if current_group:
                    groups.append(current_group)
                    current_group = []
                # Blocking task gets its own group
                groups.append([task])
                
        if current_group:
            groups.append(current_group)
            
        return groups

# Global Instance
parallel_manager = ParallelManager()
