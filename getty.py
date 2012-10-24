from datetime import datetime
from re import match
from time import time
from uuid import uuid4
from warnings import warn
from requests import post
from simplejson import dumps
from pytz import FixedOffset

__version__ = '0.1.0'

class GettyException(Exception):
    pass

class GettyImage(object):
    def __init__(self, data):
        self.id = data['ImageId']
        self.caption = data['Caption']
        self.title = data['Title']
        self.artist = data['Artist']

        self.url = data['UrlComp']
        self.preview = data['UrlPreview']
        self.thumbnail = data['UrlThumb']

        self.created = self.__to_datetime(data['DateCreated'])
        self.published = self.__to_datetime(data['DateSubmitted'])

    def __to_datetime(self, json_date):
        matches = match('/Date\(([0-9]+)(([\-+])([0-9]{2})([0-9]{2}))?\)/', json_date)
        tz = FixedOffset(
            (int(matches.group(4).lstrip('0') or 0) * 60 + int(matches.group(5).strip('0') or 0)) * int('%s1' % matches.group(3))
        )
        return datetime.fromtimestamp(int(matches.group(1)) // 1000, tz=tz)

    def __str__(self):
        return self.url

    def __repr__(self):
        return '<%s[%s] "%s">' % (self.__class__.__name__, self.id, self.url)

class GettyCollection(list):
    def __init__(self, data):
        self.page = data['ItemStartNumber']
        self.total = data['ItemTotalCount']
        self.count = data['ItemCount']

        super(GettyCollection, self).__init__([
            GettyImage(image) for image in data['Images']
        ])

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
            return self.secure

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
        elif not self._token.valid:
            self._renew_session()
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
        if status == 'warning':
            warn(' '.join(status['Message'] for status in response['ResponseHeader']['StatusList']))
            status = 'success'
        if status == 'success':
            del response['ResponseHeader']
            return response

        raise GettyException(' '.join(status['Message'] for status in response['ResponseHeader']['StatusList']))

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
        _count = count

        counts = map(int, '1,2,3,4,5,6,10,12,15,20,25,30,50,60,75'.split(','))
        if count not in counts:
            try:
                count = filter(lambda x: x > count, counts)[0]
            except IndexError:
                count = counts[-1]

        result = self._request(
            "http://connect.gettyimages.com/v1/search/SearchForImages",
            SearchForImages2RequestBody={
                'Filter': {
                    'LicensingModels': ['RoyaltyFree'],
                    'FileTypes': ['jpg'],
                    'ImageFamilies': ['creative'],
                },
                'Query': {
                    'SearchPhrase': query,
                },
                'ResultOptions': {
                    'ItemCount': count,
                    'ItemStartNumber': page,
                    'IncludeKeywords': True,
                }
            }
        )['SearchForImagesResult']

        return GettyCollection(result)[:_count]
