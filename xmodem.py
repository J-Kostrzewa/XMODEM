import serial.tools.list_ports
import serial.serialutil
import time
import os
import sys
import argparse
import ctypes
from enum import Enum

# XMODEM Protocol Constants
SOH = b'\x01'  # Start of Header
EOT = b'\x04'  # End of Transmission
ACK = b'\x06'  # Acknowledge
NAK = b'\x15'  # Negative Acknowledge
CAN = b'\x18'  # Cancel
C = b'\x43'    # ASCII 'C' - used for CRC mode
PADDING = b'\x1a'  # Padding byte

# Protocol settings
BLOCK_SIZE = 128
RETRY_LIMIT = 10
RECV_TIMEOUT = 10  # seconds

class ChecksumType(Enum):
    BASIC = 1
    CRC = 2

def calculate_checksum(data):
    """Calculate the basic XMODEM checksum (8-bit sum)"""
    return sum(data) & 0xFF

def calculate_crc(data):
    """Calculate the 16-bit CRC-CCITT used by XMODEM"""
    crc = 0
    for byte in data:
        crc = crc ^ (byte << 8)
        for _ in range(8):
            if crc & 0x8000:
                crc = (crc << 1) ^ 0x1021
            else:
                crc = crc << 1
        crc = crc & 0xFFFF
    return crc

def configure_serial_port(port, baudrate=9600, timeout=1):
    """Configure and open serial port"""
    try:
        ser = serial.Serial(
            port=port,
            baudrate=baudrate,
            bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
            timeout=timeout,
            xonxoff=False,
            rtscts=False,
            dsrdtr=False
        )
        return ser
    except serial.serialutil.SerialException as e:
        print(f"Error configuring serial port: {e}")
        return None

def send_file(ser, filename, checksum_type=ChecksumType.CRC):
    """Send a file using XMODEM protocol"""
    try:
        with open(filename, 'rb') as file:
            file_content = file.read()
    except FileNotFoundError:
        print(f"File {filename} not found.")
        return False
    except IOError as e:
        print(f"Error reading file: {e}")
        return False
    
    # Pad the data to be a multiple of BLOCK_SIZE
    padding_size = BLOCK_SIZE - (len(file_content) % BLOCK_SIZE)
    if padding_size < BLOCK_SIZE:
        file_content += PADDING * padding_size
    
    # Split data into blocks
    blocks = [file_content[i:i+BLOCK_SIZE] for i in range(0, len(file_content), BLOCK_SIZE)]
    
    print(f"Sending {filename} ({len(blocks)} blocks)...")
    
    # Wait for receiver to initiate transfer
    start_time = time.time()
    initiate_char = None
    while initiate_char is None and time.time() - start_time < RECV_TIMEOUT:
        data = ser.read(1)
        if data:
            initiate_char = data
            break
    
    if not initiate_char:
        print("Timeout waiting for receiver to initiate transfer.")
        return False
    
    use_crc = (initiate_char == C and checksum_type == ChecksumType.CRC)
    
    block_number = 1
    for block in blocks:
        retries = 0
        while retries < RETRY_LIMIT:
            # Build packet
            packet = SOH
            packet += bytes([block_number & 0xFF])  # Block number
            packet += bytes([255 - (block_number & 0xFF)])  # 1's complement of block number
            
            packet += block  # Data block
            
            if use_crc:
                crc_value = calculate_crc(block)
                packet += bytes([(crc_value >> 8) & 0xFF])  # CRC high byte
                packet += bytes([crc_value & 0xFF])        # CRC low byte
            else:
                packet += bytes([calculate_checksum(block)])  # Checksum byte
            
            # Send the packet
            ser.write(packet)
            ser.flush()
            
            # Wait for ACK/NAK
            response = ser.read(1)
            if response == ACK:
                break  # Block was received successfully
            elif response in (NAK, C):
                retries += 1
                print(f"Block {block_number} NAK received, retrying ({retries}/{RETRY_LIMIT})...")
            elif response == CAN:
                print("Transfer canceled by receiver.")
                return False
            else:
                # No response or unrecognized, retry
                retries += 1
                print(f"No valid response for block {block_number}, retrying ({retries}/{RETRY_LIMIT})...")
                
        if retries >= RETRY_LIMIT:
            print(f"Failed to send block {block_number} after {RETRY_LIMIT} retries.")
            # Send CAN to abort
            ser.write(CAN + CAN)
            return False
        
        block_number = (block_number + 1) % 256
        
    # Send EOT to indicate end of transmission
    retries = 0
    while retries < RETRY_LIMIT:
        ser.write(EOT)
        response = ser.read(1)
        if response == ACK:
            print("File transfer completed successfully.")
            return True
        retries += 1
        time.sleep(1)
        
    print("Failed to get EOT acknowledgement.")
    return False

def receive_file(ser, output_filename, checksum_type=ChecksumType.CRC):
    """Receive a file using XMODEM protocol"""
    use_crc = (checksum_type == ChecksumType.CRC)
    
    # Initiate transfer
    retries = 0
    while retries < RETRY_LIMIT:
        if use_crc:
            ser.write(C)  # Request CRC mode
        else:
            ser.write(NAK)  # Request checksum mode
        
        # Check for SOH (start of header)
        data = ser.read(1)
        if data == SOH:
            break  # Sender has started transmission
        elif data == CAN:
            print("Transfer canceled by sender.")
            return False
        
        retries += 1
        time.sleep(1)
        
    if retries >= RETRY_LIMIT:
        print(f"No response after {RETRY_LIMIT} attempts.")
        return False
    
    print("Transfer initiated, receiving data...")
    received_data = bytearray()
    expected_block = 1
    
    while True:
        # We've already read SOH, now read block number and complement
        block_num = ser.read(1)
        if not block_num:
            print("Timeout reading block number.")
            ser.write(NAK)
            continue
        
        block_num_complement = ser.read(1)
        if not block_num_complement:
            print("Timeout reading block number complement.")
            ser.write(NAK)
            continue
        
        # Verify block number and complement
        if ord(block_num) + ord(block_num_complement) != 255:
            print("Block number verification failed.")
            ser.write(NAK)
            continue
        
        # Read data block
        data_block = ser.read(BLOCK_SIZE)
        if len(data_block) != BLOCK_SIZE:
            print("Timeout reading data block.")
            ser.write(NAK)
            continue
        
        # Read checksum or CRC
        if use_crc:
            crc_bytes = ser.read(2)
            if len(crc_bytes) != 2:
                print("Timeout reading CRC.")
                ser.write(NAK)
                continue
            received_crc = (crc_bytes[0] << 8) | crc_bytes[1]
            calculated_crc = calculate_crc(data_block)
            if received_crc != calculated_crc:
                print(f"CRC error. Got {received_crc}, calculated {calculated_crc}.")
                ser.write(NAK)
                continue
        else:
            checksum = ser.read(1)
            if not checksum:
                print("Timeout reading checksum.")
                ser.write(NAK)
                continue
            calculated_checksum = calculate_checksum(data_block)
            if ord(checksum) != calculated_checksum:
                print(f"Checksum error. Got {ord(checksum)}, calculated {calculated_checksum}.")
                ser.write(NAK)
                continue
        
        # Block received correctly
        if ord(block_num) == expected_block:
            received_data.extend(data_block)
            ser.write(ACK)
            expected_block = (expected_block + 1) % 256
        elif ord(block_num) == ((expected_block - 1) % 256):
            # Duplicate block, ACK but don't include data
            ser.write(ACK)
        else:
            # Out of sequence, cancel transfer
            print(f"Out of sequence block. Expected {expected_block}, got {ord(block_num)}.")
            ser.write(CAN)
            ser.write(CAN)
            return False
        
        # Check for EOT (end of transmission)
        data = ser.read(1)
        if data == EOT:
            ser.write(ACK)
            break
        elif data == SOH:
            # This is the start of the next block
            continue
        elif not data:
            # No data received, check for timeout or wait for next block
            continue
    
    # Remove padding bytes
    while received_data and received_data[-1] == PADDING[0]:
        received_data.pop()
    
    # Write the received data to file
    try:
        with open(output_filename, 'wb') as file:
            file.write(received_data)
        print(f"File saved as {output_filename}.")
        return True
    except IOError as e:
        print(f"Error writing file: {e}")
        return False

def main():
    parser = argparse.ArgumentParser(description='XMODEM file transfer protocol')
    parser.add_argument('mode', choices=['send', 'receive'], help='Mode: send or receive')
    parser.add_argument('--port', help='Serial port name (e.g., COM1)')
    parser.add_argument('--file', help='File to send or filename to save received data')
    parser.add_argument('--baudrate', type=int, default=9600, help='Baudrate (default: 9600)')
    parser.add_argument('--checksum', choices=['basic', 'crc'], default='crc', 
                        help='Checksum type: basic or crc (default: crc)')
    
    args = parser.parse_args()
            
    # Walidacja argumentów dla trybów send/receive
    if not args.port:
        print("Error: port argument is required for send/receive mode")
        return
    if not args.file:
        print("Error: file argument is required for send/receive mode")
        return
    
    # Configure serial port
    ser = configure_serial_port(args.port, args.baudrate)
    if not ser:
        return
    
    checksum_type = ChecksumType.CRC if args.checksum == 'crc' else ChecksumType.BASIC
    
    try:
        if args.mode == 'send':
            send_file(ser, args.file, checksum_type)
        else:  # receive
            receive_file(ser, args.file, checksum_type)
    finally:
        ser.close()

if __name__ == "__main__":
    main()
