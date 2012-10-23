from time import time
from uuid import uuid4
from requests import post
from simplejson import dumps

class GettyToken(object):
    def __init__(self, timestamp=0, parameters={}):
        self.activated = bool(len(parameters))

        if self.activated:
            self.expires = timestamp + 60 * int(parameters['TokenDurationMinutes'])
            self.standard = parameters['Token']
            self.secure = parameters['SecureToken']

    def get_for(self, url):
        if not self.activated:
            return None

        if url.startswith('https'):
            print 'Using Secure Token'
            return self.secure

        print 'Using Standard Token'
        return self.standard

    @property
    def valid(self):
        return self.activated and time() < self.expires

class GettyClient(object):
    def __init__(self, system_id, system_password, user_name, user_password):
        self.system_id = system_id
        self.system_password = system_password
        self.user_name = user_name
        self.user_password = user_password

        self._token = GettyToken()

    @property
    def token(self):
        if not self._token.activated:
            self._create_session()
            print 'Token Created'
        elif not self._token.valid:
            self._renew_session()
            print 'Token Renewed'
        return self._token

    def _request(self, url, check=True, **additional):
        payload = {
            'RequestHeader': {
                'Token': (self.token if check else self._token).get_for(url),
                'CoordinationId': str(uuid4()),
            },
        }

        payload.update(additional)
        answer = post(url, data=dumps(payload), headers={'content-type': 'application/json'})
        response = answer.json
        status = response['ResponseHeader']['Status'].lower()

        print 'URL'
        print url
        print 'REQUEST'
        print payload
        print 'RESPONSE'
        print response

        if status == 'success':
            del response['ResponseHeader']
            return response

    def _create_session(self):
        self._token = GettyToken(time(), self._request(
            "https://connect.gettyimages.com/v1/session/CreateSession", check=False,
            CreateSessionRequestBody={
                'SystemId': self.system_id,
                'SystemPassword': self.system_password,
                'UserName': self.user_name,
                'UserPassword': self.user_password
            }
        )['CreateSessionResult'])

    def _renew_session(self):
        self._token = GettyToken(time(), self._request(
            "https://connect.gettyimages.com/v1/session/RenewSession", check=False,
            RenewSessionRequestBody={
                'SystemId': self.system_id,
                'SystemPassword': self.system_password,
            }
        )['RenewSessionResults'])

    def search(self, query, count=10, page=1):
        result = self._request(
            "http://connect.gettyimages.com/v1/search/SearchForImages",
            SearchForImages2RequestBody={
                'Filter': {},
                'Query': {
                    'SearchPhrase': query,
                },
                'ResultOptions': {
                    'ItemCount': count,
                    'ItemStartNumber': page,
                }
            }
        )
        return result

if __name__ == '__main__':
    gc = GettyClient(system_id, system_password, username, password)
    print gc.search('banana')
