import os
import sys
import time
import hashlib
import logging
import optparse
import requests
import ConfigParser
from requests.auth import HTTPBasicAuth

class OperationalError(Exception):
    pass


def setup_logger(name, level='ERROR', fmt='%(asctime)s [%(levelname)-5.5s]:  %(message)s', path=None):
    try:
        # resolve textual level to numerical 
        level = getattr(logging, level)
    except Exception:
        raise OperationalError('wrong logging level {l}'.format(l=level))
    logger = logging.Logger(name, level)
    formatter = logging.Formatter(fmt)
    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setLevel(level)
    stream_handler.setFormatter(formatter)
    logger.addHandler(stream_handler)
    if path:
        file_handler = logging.FileHandler(path)
        file_handler.setLevel(level)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    return logger


def setup_option_parser(conf_section):
   usage = '%prog --conf'
   parser = optparse.OptionParser(usage=usage)
   parser.add_option('-c', '--conf', type='str', help='path to a conf file')
   parser.add_option('-s', '--conf-section', type='str', help='section in configuration file', default=conf_section)
   parser.add_option('-l', '--log-file', type='str', help='path to a log file', default=None)
   parser.add_option('-L', '--log-level', type='str', help='levels available: DEBUG,INFO,WARNING,ERROR,CRITICAL', default='ERROR')
   opts, args = parser.parse_args()
   if not opts.conf:
       raise OperationalError('configuration file is a required argument')
   if not os.path.isfile(opts.conf):
       raise OperationalError('file {c} do not exists'.format(c=opts.conf))
   return opts, args


def teamcity_api(method, url, username, password, headers={'Accept': 'application/json'}):
    '''
    makes api call against teamcity server and return parsed json 
    
    url     -- api query URL
    headers -- Accept: 'application/json' is required to get json response from teamcity
    return  -- response text and response code (200, 404, e.g.)
    '''
    auth = HTTPBasicAuth(username, password)
    try:
        resp = method(url, headers=headers, auth=auth)
    except Exception as ex:
        err = 'teamcity_api failed:\n'
        err += 'exception: {message}\n'.format(message=ex.message)
        err += 'request url: {url}\n'.format(url=url)
        err += 'response code: {code}\n'.format(code=resp.status_code)
        err += 'response text: {text}'.format(text=resp.text)
        raise OperationalError(err)
    return resp.text, resp.status_code


def teamcity_api_backup_do(url, username, password, file_name):
    '''
    start teamcity backup - configs and database (no logs)

    url         -- teamcity base url (e.g. - http://tc-01)
    username    -- teamcity user 
    password    -- teamcity pass
    file_name   -- backup will be saved with this file name
    return      -- text and status_code
    '''
    api_url = '{u}/app/rest/server/backup'.format(u=url)
    api_url += '?includeConfigs=true'
    api_url += '&includeDatabase=true'
    api_url += '&addTimestamp=false'
    api_url += '&fileName={f}'.format(f=file_name)
    text, code = teamcity_api(requests.post, api_url, username, password, headers={})
    return text, code


def teamcity_api_backup_status(url, username, password):
    '''
    start teamcity backup - configs and database (no logs)

    url         -- teamcity base url (e.g. - http://tc-01)
    username    -- teamcity user 
    password    -- teamcity pass
    file_name   -- backup will be saved with this file name
    return      -- text and status_code
    '''
    api_url = '{u}/app/rest/server/backup'.format(u=url)
    text, code = teamcity_api(requests.get, api_url, username, password, headers={})
    return text, code


def teamcity_api_backup_download(url, username, password, file_name, path):
    '''
    download backup from teamcity to local storage 

    url         -- teamcity base url (e.g. - http://tc-01)
    username    -- teamcity user 
    password    -- teamcity pass
    file_name   -- backup file with wish download
    path        -- local path to file to save
    '''
    auth = HTTPBasicAuth(username, password)
    api_url = '{u}/get/file/backup/{f}'.format(u=url, f=file_name)
    resp = requests.get(api_url, stream=True, auth=auth)
    with open(path, 'wb') as fh:
        for chunk in resp.iter_content(chunk_size=512):
            if chunk:  # filter out keep-alive new chunks
                fh.write(chunk)


def artifactory_api(method, url, username, password, **kwargs):
    '''
    call to artifactory api

    url      -- url to api endpoint
    username -- artifactory user
    password -- artifactory pass
    return   -- response text and status code (200, 301 and etc)
    '''
    auth = HTTPBasicAuth(username, password)
    try:
        resp = method(url, auth=auth, **kwargs)
    except Exception as ex:
        err = 'artifactory_api failed:\n'
        err += 'exception: {message}\n'.format(message=ex.message)
        err += 'request url: {url}\n'.format(url=url)
        err += 'response code: {code}\n'.format(code=resp.status_code)
        err += 'response text: {text}'.format(text=resp.text)
        raise OperationalError(err)
    return resp.text, resp.status_code


def artifactory_api_upload(method, url, username, password, path):
    '''
    upload artifact to repositry

    method      -- reference to requests methods (e.g. requests.get)
    url         -- destination url (include repository and file_name)
    username    -- artifactory user (with perms to repositry)
    password    -- artifactory pass
    path        -- path to local file
    return      -- text and status_code
    '''
    headers = {'Content-Type': 'application/octet-stream',
               'X-Checksum-Md5': hashlib.md5(open(path).read()).hexdigest(),
               'X-Checksum-Sha1': hashlib.sha1(open(path).read()).hexdigest()}
    with open(path, 'rb') as fd:
        text, code = artifactory_api(method, url, username, password, headers=headers, data=fd)
    if code != 201:
        raise OperationalError('failed to upload: {t}'.format(t=text))
    return text, code


if __name__ == '__main__':
    # read config
    opts, args = setup_option_parser('teamcity_backup')
    # setup logger
    logger = setup_logger(name='teamcity_backup', level=opts.log_level, path=opts.log_file)
    conf = ConfigParser.ConfigParser()
    try:
        conf.read(opts.conf)
        file_prefix = conf.get(opts.conf_section, 'file_prefix')
        timestamp = time.strftime('%Y%m%d_%H%M%S')
        file_name = '{p}_{t}.zip'.format(p=file_prefix, t=timestamp)
        file_path = conf.get(opts.conf_section, 'file_path')
        file_path = os.path.join(file_path, file_name)
        teamcity_url = conf.get(opts.conf_section, 'teamcity_url').strip('/')
        teamcity_user = conf.get(opts.conf_section, 'teamcity_user')
        teamcity_pass = conf.get(opts.conf_section, 'teamcity_pass')
        artifactory_url = conf.get(opts.conf_section, 'artifactory_url')
        artifactory_url = '{u}{f}'.format(u=artifactory_url, f=file_name)
        artifactory_user = conf.get(opts.conf_section, 'artifactory_user')
        artifactory_pass = conf.get(opts.conf_section, 'artifactory_pass')
    except Exception as ex:
        logger.error('failed to parse config file. {e}'.format(e=ex))
        sys.exit(1)
    # start backup
    logger.info('starting backup ...')
    try:
        text, code = teamcity_api_backup_do(teamcity_url, teamcity_user, teamcity_pass, file_name)
    except Exception as ex:
        logger.error(ex)
        sys.exit(1)
    logger.info('backup starter got: {t}; {c} ...'.format(t=text, c=code))
    while True:
        # poll for status
        logger.info('polling backup ...')
        try:
            text, code = teamcity_api_backup_status(teamcity_url, teamcity_user, teamcity_pass)
        except Exception as ex:
            logger.error(ex)
        logger.info('backup poller got: {t}; {c} ...'.format(t=text, c=code))
        if 'idle' in text.lower():
            break
        time.sleep(10)
    # download backup
    logger.info('downloading backup to {f} ...'.format(f=file_path))
    try:
        teamcity_api_backup_download(teamcity_url, teamcity_user, teamcity_pass, file_name, file_path)
    except Exception as ex:
        logger.error(ex)
        sys.exit(1)
    # upload to artifactory
    logger.info('uploading {f} to artifactory {a} ...'.format(f=file_path, a=artifactory_url))
    try:
        text, code = artifactory_api_upload(requests.put, artifactory_url, artifactory_user, artifactory_pass, file_path)
    except Exception as ex:
        logger.error(ex)
        sys.exit(1)
    logger.info('artifactory uploader got: {t}; {c} ...'.format(t=text, c=code))
    os.unlink(file_path)
    sys.exit(0)
