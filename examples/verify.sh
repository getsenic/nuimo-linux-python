
# Script to verify correct operation of Nuimo Controller

cmd=$1

case "$cmd" in
    install)
	echo "Install Bluez and other utilities if not already installed"
	sudo apt-get install --no-install-recommends bluetooth timeout
	# Shows the version of the installed bluez. **bluetoothd** daemon must run at startup to use Bluez
	echo "bluez version: $(bluetoothd --version)"
	;;

    scan)
	echo "Enable Bluetooth dongle hci0 if not already enabled"
	sudo hciconfig hci0 up
	echo "Scan for any Bluetooth LE devices, wait for 5 seconds"
	sudo timeout -s SIGINT 5s hcitool lescan
	which bluetoothctl && bluetoothctl devices # (Lists the previously paired peripherals)
	;;

    connect)
	echo "Manually connect to Nuimo with bluez"
	echo "Scanning for 5 seconds"
	nuimo_mac=$(sudo timeout -s SIGINT 5s hcitool lescan | grep Nuimo | head -1 | sed 's/ *Nuimo//')
	echo "First Nuimo found at $nuimo_mac"
	echo 'connect\ncharacteristics'
	gatttool -b "$nuimo_mac" -t random --characteristics
	
	;;
    *)
	echo "Usage: verify.sh [install | scan]"
	;;
esac
