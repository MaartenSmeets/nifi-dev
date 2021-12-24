#Desktop
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo apt-key add -
apt-cache policy docker-ce

#Also xenial for old Docker version for running Minikube locally 
add-apt-repository "deb [arch=amd64] https://download.docker.com/linux/ubuntu focal stable"

apt-get update
apt-get install --no-install-recommends ubuntu-desktop
apt-get -y install aptitude
aptitude -y install --without-recommends ubuntu-desktop 
apt-get -y install gnome-session gnome-terminal tasksel terminator firefox jq apt-transport-https ca-certificates gnupg2 curl software-properties-common docker-ce docker-compose libxss1 libgconf-2-4 evince socat maven openjdk-11-jdk xfonts-terminus fonts-terminus console-terminus mlocate
apt-get -y install --reinstall debconf
tasksel install ubuntu-desktop-minimal

#Fix root not allowed to start X-window
xhost local:root


#Remove font issue
#rm /etc/fonts/fonts.conf
#rm /etc/fonts/conf.d/10-hinting-*.conf
#ln -sv /etc/fonts/conf.avail/10-hinting-full.conf /etc/fonts/conf.d/

#developer user
useradd -d /home/developer -m developer
echo -e "Welcome01\nWelcome01" | passwd developer
usermod -a -G vboxsf developer
usermod -a -G docker developer
usermod -a -G sudo developer
usermod --shell /bin/bash developer

#Fix screen flickering issue
#perl -e '$^I=".backup";while(<>){s/#(WaylandEnable=false)/$1/;print;}' /etc/gdm3/custom.conf

#Hide vagrant
echo '[User]' > /var/lib/AccountsService/users/vagrant
echo 'SystemAccount=true' >> /var/lib/AccountsService/users/vagrant

cp /etc/sudoers.d/vagrant /etc/sudoers.d/developer
sed -i 's/vagrant/developer/g' /etc/sudoers.d/developer

apt-get autoremove
apt-get clean

#Kafka local prefer docker-compose
#useradd -d /home/kafka -m kafka
#mkdir /home/kafka/Downloads
#echo -e "Welcome01\nWelcome01" | passwd kafka
#usermod --shell /bin/bash kafka
#curl "https://downloads.apache.org/kafka/3.0.0/kafka_2.13-3.0.0.tgz" -o /home/kafka/Downloads/kafka.tgz
#tar -xzf /home/kafka/Downloads/kafka.tgz -C /usr/local
#ln -s /usr/local/kafka_2.13-3.0.0 /usr/local/kafka
#mkdir -p /usr/local/kafka/logs
#chown -R kafka:kafka /usr/local/kafka_2.13-3.0.0

#Starting the server and creating a topic
#sudo -u kafka /usr/local/kafka/bin/zookeeper-server-start.sh /usr/local/kafka/config/zookeeper.properties
#sudo -u kafka /usr/local/kafka/bin/kafka-server-start.sh /usr/local/kafka/config/server.properties
#sudo -u kafka /usr/local/kafka/bin/kafka-topics.sh --create --partitions 1 --replication-factor 1 --topic quickstart-events --bootstrap-server localhost:9092

mkdir /home/developer/comp
cp /vagrant/Dockerfile /home/developer/comp
cp /vagrant/docker-compose.yml /home/developer/comp
cp /vagrant/broker-list.sh /home/developer/comp
cp /vagrant/create-topics.sh /home/developer/comp
cp /vagrant/download-kafka.sh /home/developer/comp
cp /vagrant/start-kafka.sh /home/developer/comp
cp /vagrant/versions.sh /home/developer/comp
cp -R /vagrant/overrides /home/developer/comp/overrides

chown -R developer:developer /home/developer/comp
cd /home/developer/comp
docker-compose pull -q

curl https://www.kafkatool.com/download2/offsetexplorer.sh -o /home/developer/kafkatool.sh
chown developer:developer /home/developer/kafkatool.sh

shutdown now -h