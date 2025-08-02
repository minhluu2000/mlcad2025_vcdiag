import asyncio
import websockets
import json
from typing import Dict, List
from queue import Queue
from threading import Thread, Event, Lock
from .types import *

class PipelineWebSocket:
    def __init__(self, port: int = 7500):
        self.port = port
        self.connected_clients = set()
        self.message_queue = Queue()
        self._running = True
        self._server_ready = Event()
        self._client_connected = Event()
        self._clients_lock = Lock()
        
        # Start background event loop in a separate thread
        self.server_thread = Thread(target=self._run_server, daemon=True)
        self.server_thread.start()
        
        # Wait for server to be ready
        self._server_ready.wait()

    def _run_server(self):
        """Runs the websocket server in a background thread"""
        # Create and set the event loop for this thread
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

        # Create and start the server
        async def start_server():
            server = await websockets.serve(self.register, "localhost", self.port)
            self._server_ready.set()
            await server.wait_closed()

        # Start message processing loop
        async def run_server():
            await asyncio.gather(
                start_server(),
                self._process_queue()
            )

        try:
            self.loop.run_until_complete(run_server())
        except Exception as e:
            print(f"Server error: {e}")
        finally:
            self.loop.close()

    async def _process_queue(self):
        """Processes messages from the queue and broadcasts them"""
        while self._running:
            try:
                # Process all available messages
                while not self.message_queue.empty():
                    message = self.message_queue.get_nowait()
                    await self.broadcast(message)
                    self.message_queue.task_done()
                
                # Yield control to allow other tasks to run
                await asyncio.sleep(0.01)
            except Exception as e:
                print(f"Error processing message queue: {e}")

    async def register(self, websocket):
        """Handles websocket client registration"""
        with self._clients_lock:
            self.connected_clients.add(websocket)
            if len(self.connected_clients) > 0:
                self._client_connected.set()
            print(f"Client connected. Total clients: {len(self.connected_clients)}")

        try:
            await websocket.wait_closed()
        finally:
            with self._clients_lock:
                self.connected_clients.remove(websocket)
                if len(self.connected_clients) == 0:
                    self._client_connected.clear()
                print(f"Client disconnected. Total clients: {len(self.connected_clients)}")
    
    def wait_for_clients(self, timeout: float = None) -> bool:
        """
        Wait for at least one client to connect.
        
        Args:
            timeout (float, optional): Maximum time to wait in seconds. None means wait forever.
            
        Returns:
            bool: True if a client connected, False if timeout occurred
        """
        return self._client_connected.wait(timeout=timeout)

    def has_clients(self) -> bool:
        """Check if there are any connected clients"""
        with self._clients_lock:
            return len(self.connected_clients) > 0

    def get_client_count(self) -> int:
        """Get the number of connected clients"""
        with self._clients_lock:
            return len(self.connected_clients)

    def _queue_message(self, message: Dict):
        """Adds a message to the queue"""
        self.message_queue.put(message)

    def set_current_process(self, process_name: str):
        """Synchronously queues a process update message"""
        message = {
            "type": "set_current_process",
            "payload": {
                "processName": process_name
            }
        }
        self._queue_message(message)
    
    def update_stats(self, stats: Stats):
        message = {
            "type": "update_stats",
            "payload": {
                "stats": stats.model_dump()
            }
        }
        self._queue_message(message)

    def split_file(self, regions: List[Region]):
        """Synchronously queues a file split message"""
        message = {
            "type": "split_file",
            "payload": {
                "regions": [region.model_dump() for region in regions]
            }
        }
        self._queue_message(message)

    def select_region(self, region_index: int):
        """Synchronously queues a region selection message"""
        message = {
            "type": "select_region",
            "payload": {
                "selectedRegion": region_index
            }
        }
        self._queue_message(message)

    def select_bug(self, bug: Bug, line: VerilogLine):
        """Synchronously queues a bug selection message"""
        message = {
            "type": "select_bug",
            "payload": {
                "bug": bug.model_dump(),
                "line": line.model_dump()
            }
        }
        self._queue_message(message)

    def mutate_line(self, mutated_line: VerilogLine):
        """Synchronously queues a line mutation message"""
        message = {
            "type": "mutate_line",
            "payload": {
                "mutatedLine": mutated_line.model_dump()
            }
        }
        self._queue_message(message)

    def evaluate(self, result: EvaluationResult):
        """Synchronously queues an evaluation result message"""
        message = {
            "type": "evaluate",
            "payload": {
                "result": result.model_dump()
            }
        }
        self._queue_message(message)

    async def broadcast(self, message: Dict):
        """Broadcasts a message to all connected clients"""
        if self.connected_clients:
            await asyncio.gather(
                *[client.send(json.dumps(message)) for client in self.connected_clients]
            )

    def shutdown(self):
        """Cleanly shuts down the websocket server"""
        self._running = False
        if hasattr(self, 'loop') and self.loop.is_running():
            self.loop.call_soon_threadsafe(self.loop.stop)
        if self.server_thread.is_alive():
            self.server_thread.join()