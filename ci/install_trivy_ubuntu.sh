apt-get update
CODE_NAME=`lsb_release -c|cut -d ":" -f 2`
apt-get install apt-transport-https gnupg -y
wget -qO - https://aquasecurity.github.io/trivy-repo/deb/public.key | apt-key add -
echo deb https://aquasecurity.github.io/trivy-repo/deb $CODE_NAME main | tee -a /etc/apt/sources.list.d/trivy.list
apt-get update
apt-get install trivy -y
