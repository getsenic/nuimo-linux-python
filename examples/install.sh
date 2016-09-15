
# Script to install Nuimo support

cmd=$1

case "$cmd" in
    install)
	echo "Install Bluez and other utilities if not already installed"
	set -x
	sudo apt-get install --no-install-recommends bluetooth timeout
	# Shows the version of the installed bluez. **bluetoothd** daemon must run at startup to use Bluez
	echo "bluez version: $(bluetoothd --version)"
	;;

    scan)
	echo "Enable Bluetooth dongle hci0 if not already enabled"
	set -x
	sudo hciconfig hci0 up
	set +x
	echo "Scan for any Bluetooth LE devices, wait for 5 seconds"
	set -x
	sudo timeout -s SIGINT 5s hcitool lescan
	which bluetoothctl && bluetoothctl devices # (Lists the previously paired peripherals)
	;;

    connect)
	echo "Manually connect to Nuimo with bluez"
	echo "Scanning for 5 seconds"
	nuimo_mac=$(sudo timeout -s SIGINT 5s hcitool lescan | awk '$2 == "Nuimo" {print $1; exit}')
	echo "First Nuimo found at $nuimo_mac"
	echo "Getting button click handle"
	click_event_handle=$(gatttool -b "$nuimo_mac" -t random --characteristics |
	    awk -F, 'BEGIN {button_id = "f29b1529"};
                     $0 ~ button_id {
                        split($3, button, " ");
                        handle=button[5];
                        printf "0x%x\n", strtonum(handle) + 1
                     }')
	echo "Activate handle $click_event_handle for button press events"
	echo "click Nuimo button, use Ctrl+C to exit"
	gatttool -b "$nuimo_mac" -t random --char-write-req --handle=$click_event_handle --value=0100 --listen
	;;

    pygattlib)
	echo "Installing Pygattlib and dependencies"
	set -x
	sudo apt-get install pkg-config libboost-python-dev libboost-thread-dev libbluetooth-dev libglib2.0-dev python-dev
	[ ! -d pygattlib ] && git clone https://github.com/matthewelse/pygattlib
	cd pygattlib && sudo python setup.py install
	;;

    py3gattlib)
	echo "Installing Pygattlib and dependencies for Python 3"
	set -x
	sudo apt-get install pkg-config libboost-python-dev libboost-thread-dev libbluetooth-dev libglib2.0-dev python-dev
	[ ! -d pygattlib ] && git clone https://github.com/matthewelse/pygattlib
	cd pygattlib &&	sudo python3 setup.py install
	;;

    nuimosdk)
	echo "Installing Nuimo SDK"
	set -x
	[ ! -d nuimo-linux-python ] && git clone https://github.com/getsenic/nuimo-linux-python
	echo "Copy $(pwd)/nuimo-linux-python/nuimo.py to your project directory"
	;;

    test)
	echo "Testing Nuimo SDK"
	sdk="nuimo-linux-python"
	set -x
	[ -f $sdk/examples/test.py ] && { sudo PYTHONPATH=$sdk python $sdk/examples/test.py; exit 0; }
	[ -f examples/test.py ] && { sudo PYTHONPATH=. python examples/test.py; exit 0; }
        set +x
	echo "Please install the Nuimo SDK: sh $0 nuimosdk "
	;;

    *)
	echo "Usage: sh $0 [install | scan | connect | pygattlib | py3gattlib | nuimosdk | test]"
	;;

esac
