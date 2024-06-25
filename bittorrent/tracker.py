import aiohttp
import random
import logging
import socket
from struct import unpack
from urllib.parse import urlencode

import bencoding

class TrackerResponse:
    """Response from tracker after successful connection to the trackers announce URL
    """
    
    def __init__(self, response: dict):
        self.response = response
    
    @property
    def failure(self):
        if b'failure reason' in self.response:
            return self.response[b'failure reason'].decode('utf-8')
        return None
    
    @property
    def interval(self) -> int:
        """Number of seconds before making another request for client to tracker

        Returns:
            int: seconds to wait
        """
        return self.response.get(b'interval', 0)
    
    @property
    def complete(self) -> int:
        """Number of seeders with entire file

        Returns:
            int: # of seeders
        """
        return self.response.get(b'complete', 0)
    
    @property
    def incomplete(self) -> int:
        """Number of leechers

        Returns:
            int: # of leechers
        """
        return self.response.get(b'incomplete', 0)
    
    @property
    def peers(self):
        """List of tuples for each peer structured as (ip, port)
        """
        peers = self.response[b'peers']
        if type(peers) == list:
            # TODO: Implement support for dictionary peers
            logging.debug('Dictionary peers not supported')
            raise NotImplementedError()
        else:
            logging.debug('List peers supported')
            
            # Split the string in pieces of length 6 bytes, where the first
            # 4 characters is the IP the last 2 is the TCP port.
            peers = [peers[i:i+6] for i in range(0, len(peers), 6)]
            
            # convert encoded address to list of tuples
            return [(socket.inet_ntoa(peer[:4]), _decode_port(peer[4:])) for peer in peers]

    def __str__(self):
        return "incomplete: {incomplete}\n" \
               "complete: {complete}\n" \
               "interval: {interval}\n" \
               "peers: {peers}\n".format(
                   incomplete=self.incomplete,
                   complete=self.complete,
                   interval=self.interval,
                   peers=", ".join([x for (x, _) in self.peers]))
               
class Tracker:
    """A connection to a tracker for a given Torrent
    """
    
    def __init__(self, torrent):
        self.torrent = torrent
        self.peer_id = _calculate_peer_id()
        self.http_client = aiohttp.ClientSession()
        
    async def connect(self, first: bool = None, uploaded: int = 0, downloaded: int = 0):
        """
        Announce to tracker + get list of peers to connect to. Update list of peers if call is successful.

        :param first: Whether or not this is the first announce call
        :param uploaded: The total number of bytes uploaded
        :param downloaded: The total number of bytes downloaded
        """
        params = {
            'info_hash': self.torrent.info_hash,
            'peer_id': self.peer_id,
            'port': 6889,
            'uploaded': uploaded,
            'downloaded': downloaded,
            'left': self.torrent.total_size - downloaded,
            'compact': 1,
        }
        if first:
            params['event'] = 'started'
            
        url = self.torrent.announce + '?' + urlencode(params)
        logging.info('Connecting to tracker at: ' + url)
        
        async with self.http_client.get(url) as response:
            if not response.status == 200:
                raise ConnectionError('Unable to connect to tracker: status code {}'.format(response.status))
            data = await response.read()
            self.raise_for_error(data)
            return TrackerResponse(bencoding.Decoder(data).decode())

    def close(self):
        self.http_client.close()
        
    def raise_for_error(self, tracker_response):
        """double check that response of 200 is still bencoded correctly

        Args:
            tracker_response (bytes): response from connection to tracker
        """
        try: 
            message = tracker_response.decode("utf-8")
            if "failure" in message:
                raise ConnectionError("Tracker response: {}".format(message))
        except UnicodeDecodeError:
            pass
        
    def _construct_tracker_parameters(self):
        """
        Constructs the URL parameters used when issuing the announce call
        to the tracker.
        """
        return {
            'info_hash': self.torrent.info_hash,
            'peer_id': self.peer_id,
            'port': 6889,
            # TODO Update stats when communicating with tracker
            'uploaded': 0,
            'downloaded': 0,
            'left': 0,
            'compact': 1}

def _calculate_peer_id():
    return '-PC0001-' + ''.join(
        [str(random.randint(0, 9)) for _ in range(12)])

def _decode_port(port):
    return unpack('>H', port)[0]