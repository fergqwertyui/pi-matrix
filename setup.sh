#!/bin/bash

echo "Ensure packages are installed:"
sudo apt-get install -y libopenjp2-7 python3-dbus python3-venv

echo "Blacklist soundcard..."
sudo touch /etc/modprobe.d/alsa-blacklist.conf
echo "blacklist snd_bcm2835" | sudo tee -a /etc/modprobe.d/alsa-blacklist.conf

install_path=$(pwd)
venv_path="${install_path}/venv"

echo "Creating a Python virtual environment at ${venv_path}..."
python3 -m venv $venv_path

echo "Activating virtual environment..."
source $venv_path/bin/activate

echo "Installing Python dependencies inside virtual environment:"

echo "Installing spotipy library:"
pip install spotipy==2.23.0

echo "Installing pillow library:"
pip install pillow==9.3.0

echo "Installing flask library:"
pip install flask==3.0.0

echo "Enter your Spotify Client ID:"
read spotify_client_id
export SPOTIPY_CLIENT_ID=$spotify_client_id

echo "Enter your Spotify Client Secret:"
read spotify_client_secret
export SPOTIPY_CLIENT_SECRET=$spotify_client_secret

echo "Enter your Spotify Redirect URI:"
read spotify_redirect_uri
export SPOTIPY_REDIRECT_URI=$spotify_redirect_uri

echo "Enter your Spotify username:"
read spotify_username

echo "Generating Spotify token..."
${venv_path}/bin/python python/generateToken.py $spotify_username

echo
echo "###### Spotify Token Created ######"
echo "Filename: .cache"

echo "Enter the full path to your Spotify token:"
read spotify_token_path

echo "Downloading rgb-matrix software setup:"
curl https://raw.githubusercontent.com/adafruit/Raspberry-Pi-Installer-Scripts/master/rgb-matrix.sh > rgb-matrix.sh

sed -n '/REBOOT NOW?/q;p' < rgb-matrix.sh > rgb-matrix-spotipi.sh

echo "Running rgb-matrix software setup:"
sudo bash rgb-matrix-spotipi.sh

echo "Removing rgb-matrix setup script:"
sudo rm rgb-matrix.sh
echo "...done"

echo "Removing spotipi service if it exists:"
sudo systemctl stop spotipi
sudo rm -rf /etc/systemd/system/spotipi.*
sudo systemctl daemon-reload
echo "...done"

echo "Removing spotipi-client service if it exists:"
sudo systemctl stop spotipi-client
sudo rm -rf /etc/systemd/system/spotipi-client.*
sudo systemctl daemon-reload
echo "...done"

echo "Creating spotipi service:"
sudo cp ./config/spotipi.service /etc/systemd/system/
sudo sed -i -e "/\[Service\]/a ExecStart=${venv_path}/bin/python ${install_path}/python/displayCoverArt.py ${spotify_username} ${spotify_token_path} < /dev/zero &> /dev/null &" /etc/systemd/system/spotipi.service
sudo mkdir -p /etc/systemd/system/spotipi.service.d
spotipi_env_path=/etc/systemd/system/spotipi.service.d/spotipi_env.conf
sudo touch $spotipi_env_path
echo "[Service]" | sudo tee $spotipi_env_path
echo "Environment=\"SPOTIPY_CLIENT_ID=${spotify_client_id}\"" | sudo tee -a $spotipi_env_path
echo "Environment=\"SPOTIPY_CLIENT_SECRET=${spotify_client_secret}\"" | sudo tee -a $spotipi_env_path
echo "Environment=\"SPOTIPY_REDIRECT_URI=${spotify_redirect_uri}\"" | sudo tee -a $spotipi_env_path
echo "Environment=\"PATH=${venv_path}/bin:\$PATH\"" | sudo tee -a $spotipi_env_path
sudo systemctl daemon-reload
sudo systemctl start spotipi
sudo systemctl enable spotipi
echo "...done"

echo "Creating spotipi-client service:"
sudo cp ./config/spotipi-client.service /etc/systemd/system/
sudo sed -i -e "/\[Service\]/a ExecStart=${venv_path}/bin/python ${install_path}/python/client/app.py &" /etc/systemd/system/spotipi-client.service
sudo systemctl daemon-reload
sudo systemctl start spotipi-client
sudo systemctl enable spotipi-client
echo "...done"

echo -n "In order to finish setup a reboot is necessary..."
echo -n "REBOOT NOW? [y/N] "
read
if [[ ! "$REPLY" =~ ^(yes|y|Y)$ ]]; then
    echo "Exiting without reboot."
    deactivate
    exit 0
fi

echo "Reboot started..."
reboot
sleep infinity
