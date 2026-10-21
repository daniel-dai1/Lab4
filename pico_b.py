import sys
import time
import uselect

from machine import Pin, UART


DEVICE_NAME = "Pico B"
BAUD_RATE = 115200
KEEPALIVE_INTERVAL_MS = 10000
KEEPALIVE_PREFIX = "\x01"

identity_led = Pin("LED", Pin.OUT)
identity_led.value(0)

# UART1 links the boards over GP8/GP9; polling keeps console and UART reads non-blocking.
uart = UART(1, baudrate=9600, bits=8, parity=None, stop=1, tx=Pin(8), rx=Pin(9))
console_poll = uselect.poll()
console_poll.register(sys.stdin, uselect.POLLIN)
uart_poll = uselect.poll()
uart_poll.register(uart, uselect.POLLIN)

# Keep typed text separate from the byte buffer used to assemble received lines.
outgoing_buffer = ""
incoming_buffer = bytearray()
last_keepalive = time.ticks_ms()


def format_local_time():
	current_time = time.localtime()
	return "%04d-%02d-%02d %02d:%02d:%02d" % (
		current_time[0],
		current_time[1],
		current_time[2],
		current_time[3],
		current_time[4],
		current_time[5],
	)


def display_incoming(line):
	# The prefix distinguishes periodic status messages from chat messages.
	if line.startswith(KEEPALIVE_PREFIX):
		print("[keepalive from partner] " + line[len(KEEPALIVE_PREFIX):])
	elif line:
		print("[partner] " + line)


print("{} chat ready. Type a message and press Enter.".format(DEVICE_NAME))
print("UART1: GP8 TX, GP9 RX, {} baud.".format(BAUD_RATE))

while True:
	if console_poll.poll(0):
		character = sys.stdin.read(1)
		if character and character in ("\r", "\n"):
			if outgoing_buffer:
				# Send complete messages as UTF-8, terminated by a newline.
				uart.write(outgoing_buffer.encode("utf-8") + b"\n")
				print("[you] " + outgoing_buffer)
				outgoing_buffer = ""
				last_keepalive = time.ticks_ms()
		elif character and character in ("\x08", "\x7f"):
			outgoing_buffer = outgoing_buffer[:-1]
		elif character and character >= " ":
			outgoing_buffer += character

	if uart_poll.poll(0):
		while uart.any():
			received = uart.read(1)
			if not received:
				break
			# Decode only after a full line arrives; ignore CR in CRLF endings.
			if received == b"\n":
				display_incoming(incoming_buffer.decode("utf-8"))
				incoming_buffer = bytearray()
			elif received != b"\r":
				incoming_buffer.extend(received)

	now = time.ticks_ms()
	# ticks_diff handles the timer counter wrapping around.
	if time.ticks_diff(now, last_keepalive) >= KEEPALIVE_INTERVAL_MS:
		keepalive = KEEPALIVE_PREFIX + format_local_time() + "\n"
		uart.write(keepalive.encode("utf-8"))
		last_keepalive = now
