##### Description
- Purpose - automate backup for TeamCity servers

Basically script will run TeamCity backup, download from TeamCity server and upload to Artifactory repository.

Backup configured to run every day at 20:00 UTC (node time).

##### Prerequisites
- network access to TeamCity server
- TeamCity credentials with permission to issue api calls
- Artifactory credentials with read/write for particular repository
- python2 (2.7) and `requests` module
- virtualenv

##### Installation
Preferred to install script on TeamCity server.

```bash
# change to root
sudo su -

# create directory and copy files
mkdir /opt/teamcity_backup
mv ~ninja/teamcity_backup.* /opt/teamcity_backup/
cd /opt/teamcity_backup/

# setup virtualenv
virtualenv .pyenv
. .pyenv/bin/activate
pip install requests

# edit config file (credentials and artifactory repository)
vim teamcity_backup.cfg

# change owner and update permissions
chown ninja:ninja -R /opt/teamcity_backup/
chmod go-rwx /opt/teamcity_backup/*.cfg

# switch user and run test backup (observe script output and witness artifact existense in Artfiactory repo)
su - ninja
. .pyenv/bin/activate
python2 /opt/teamcity_backup/teamcity_backup.py --conf=/opt/teamcity_backup/teamcity_backup.cfg --log-level=INFO

# copy install and enable service
chown root:root ~ninja/teamcity-backup.*
mv ~ninja/teamcity-backup.* /lib/systemd/system/
systemctl daemon-reload
systemctl start teamcity-backup.timer
systemctl enable teamcity-backup.timer

# check that timer is listed
systemctl list-timers
```
