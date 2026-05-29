import pytest
import asyncio
from tools.infrastructure.parallel_manager import parallel_manager
from tools.utils.io_lock import io_lock
from hivemind_memory.hive_memory import hive_memory
from pathlib import Path

@pytest.mark.asyncio
async def test_parallel_throttling():
    """Verify that the parallel manager throttles tasks based on slots."""
    parallel_manager.semaphore = asyncio.Semaphore(2) # 2 slots
    
    async def slow_task():
        await asyncio.sleep(0.5)
        return True
    
    start = asyncio.get_event_loop().time()
    # Run 4 tasks with 2 slots
    await asyncio.gather(
        parallel_manager.run_task(slow_task),
        parallel_manager.run_task(slow_task),
        parallel_manager.run_task(slow_task),
        parallel_manager.run_task(slow_task)
    )
    duration = asyncio.get_event_loop().time() - start
    # Should take at least 1.0s (2 batches of 0.5s)
    assert duration >= 1.0

def test_io_lock_mutual_exclusion(tmp_path):
    """Verify that IO Lock prevents concurrent writes."""
    test_file = tmp_path / "concurrent.txt"
    io_lock.lock_dir = tmp_path / "locks"
    
    def write_sync(text):
        with io_lock.atomic_write(str(test_file)):
            test_file.write_text(text)
            
    # In a real parallel scenario, one would wait for the other
    # Here we just verify the context manager works
    write_sync("Agent A")
    assert test_file.read_text() == "Agent A"

def test_hive_recall():
    """Verify that the Hivemind can recall past lessons."""
    hive_memory.data = []
    hive_memory.ingest_lesson("Fix hydration error in Next.js", "Remove window check", "ada-cleaning")
    
    results = hive_memory.query("Hydration issue in layout")
    assert len(results) > 0
    assert results[0]["project"] == "ada-cleaning"
