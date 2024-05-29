# LaudaT2200 Tango Device Server

This is a Tango Device Server for controlling the Lauda T2200 chiller.


## Description

This Tango Device Server provides an interface for controlling and monitoring a Lauda T2200 chiller. It communicates with the chiller via a serial port, and provides a number of Tango attributes and commands for interacting with the chiller.

## Attributes

The device server provides the following Tango attributes:

- `bath_temp`: The current bath temperature of the chiller.
- `temp_setp`: The target temperature setpoint for the chiller.
- `chiller_status`: The current status of the chiller.
- `is_on`: Indicates if the chiller is on or off.
- `pressure`: The current pressure of the chiller.

## Device Properties

The device server has the following properties:

- `serialport`: The serial port to use for communication with the chiller.
- `baudrate`: The baud rate for the serial communication.
- `timeout`: The timeout for the serial communication.

## Installation

To install this device server, clone the repository and install the required dependencies.

## Usage

To run the device server, use the following command:

```bash
python LaudaT2200.py <Instance>


