import asyncio
import logging
import struct
from asyncio import Queue
from concurrent.futures import CancelledError

import bitstring

REQUEST_SIZE = 2**14

class ProtocolError(BaseException):
    pass

class PeerConnection:
    def __init__(self, queue: Queue, info_hash, peer_id, piece_manager, on_block_cb=None):
        self.my_state = []
        self.peer_state = []
        self.queue = queue
        self.info_hash = info_hash
        self.peer_id = peer_id
        self.remote_id = None
        self.writer = None
        self.reader = None
        self.piece_manager = piece_manager
        self.on_block_cb = on_block_cb
        self.future = asyncio.create_task(self._start())

    async def _start(self):
        while 'stopped' not in self.my_state:
            ip, port = await self.queue.get()
            logging.info('Got peer with : {ip}'.format(ip=ip))
            
            try:
                # TODO For some reason it does not seem to work to open a new connection if the first one drops (i.e. second loop).
                self.reader, self.writer = await asyncio.open_connection(ip, port)
                logging.info('Connection open to peer: {ip}'.format(ip=ip))
                
                buffer = await self._handshake()
                
                # TODO Add support for sending data
                # Sending BitField is optional and not needed when client does
                # not have any pieces. Thus we do not send any bitfield message
                
                # The default state for a connection is that peer is not
                # interested and we are choked
                self.my_state.append('choked')
                
                # Let the peer know we're interested in downloading pieces
                await self._send_interested()
                self.my_state.append('interested')
                
                # Start reading responses as a stream of messages for as
                # long as the connection is open and data is transmitted
                async for message in PeerStreamIterator(self.reader, buffer):
                    if 'stopped' in self.my_state:
                        break
                    if type(message) is BitField:
                        self.piece_manager.add_peer(self.remote_id, message.bitfield)
                    elif type(message) is Interested:
                        self.peer_state.append('interested')
                    elif type(message) is NotInterested:
                        self.peer_state.remove('interested')
                    elif type(message) is Choke:
                        self.my_state.append('choked')
                    elif type(message) is Unchoke:
                        if 'choked' in self.my_state:
                            self.my_state.remove('choked')
                    elif type(message) is Have:
                        self.piece_manager.update_peer(self.remote_id, message.index)
                    elif type(message) is KeepAlive:
                        pass
                    elif type(message) is Piece:
                        self.my_state.remove('pending_request')
                        self.on_block_cb(
                            peer_id = self.remote_id,
                            piece_index = message.index,
                            block_offset = message.begin,
                            data = message.block
                        )
                    elif type(message) is Request:
                        # TODO Add support for sending data
                        logging.info('Ignoring recieved Request message')
                    elif type(message) is Cancel:
                        # TODO Add support for sending data
                        logging.info('Ignoring recieved Cancel message')
                
                    if 'choked' not in self.my_state:
                        if 'interested' in self.my_state:
                            if 'pending_request' not in self.my_state:
                                self.my_state.append('pending_request')
                                await self._request_piece()
            except ProtocolError as e:
                logging.error('Protocol error: {0}'.format(e))
            except (ConnectionRefusedError, TimeoutError) as e:
                logging.error('Connection error: {0}'.format(e))
            except (ConnectionResetError, CancelledError) as e:
                logging.error('Connection reset: {0}'.format(e))
            except Exception as e:
                logging.error('Unexpected error: {0}'.format(e))
                self.cancel()
                raise e
            self.cancel()
    
    def cancel(self):
        """Sends cancel message to remote peer and close connection
        """
        logging.info('Closing peer {id}'.format(id=self.remote_id))
        if not self.future.done():
            self.future.cancel()
        if self.writer:
            self.writer.close()
            
        self.queue.task_done()
        
    def stop(self):
        """stop connection from current peer and stop connecting to new peers
        """
        self.my_state.append('stopped')
        if not self.future.done():
            self.future.cancel()
            
    async def _request_piece(self):
        block = self.piece_manager.next_request(self.remote_id)
        if block:
            message = Request(block.piece, block.offset, block.length).encode()
            
            logging.debug('Requesting block {block} for piece {piece}of {length} bytes from peer {peer}'.format(
                block=block.offset, 
                piece=block.piece, 
                length=block.length, 
                peer=self.remote_id))  
            
            self.writer.write(message)
            await self.writer.drain()
    
    async def _handshake(self):
        """Send handshake to peer and wait for peer response
        """
        self.writer.write(Handshake(self.info_hash, self.peer_id).encode())
        
        
            
            
                        

                
                



        
    