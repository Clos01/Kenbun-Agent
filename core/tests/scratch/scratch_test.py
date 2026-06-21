import sys
import os
sys.path.append(os.path.join(os.getcwd(), 'core'))

from tools.infrastructure.server import consult_supervisor
import asyncio

print(consult_supervisor("Testing the local supervisor system. Please acknowledge receipt."))
