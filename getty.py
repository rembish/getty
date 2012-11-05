from datetime import datetime
from time import time
from re import match
from uuid import uuid4
from warnings import warn

try:
    from simplejson import dumps
except ImportError:
    from json import dumps

from pytz import FixedOffset, UTC
from requests import post

GETTY_VARIANT_LAYOUT = 'layout'
GETTY_VARIANT_PREVIEW = 'preview'
GETTY_VARIANT_THUMBNAIL = 'thumbnail'
GETTY_VARIANT_LARGEST = 'largest'

class GettyException(Exception):
    pass

class GettyImageVariant(object):
    def __init__(self, image, name, url=None, id=None, watermark=False, paid=False, dimensions=(), size=None, dpi=None):
        self.name = name
        self._url = url
        self.id = id

        self.watermark = watermark
        self.paid = paid

        self.dimensions = dimensions
        self.size = size
        self.dpi = dpi

        self.owner = image

    @property
    def url(self):
        if self._url:
            return self._url

        return self.owner.client.get_urls(self)[self.owner.id]

    def __repr__(self):
        return '<%s[%s] for %s[%s]>' % (self.__class__.__name__, self.name, self.owner.__class__.__name__, self.owner.id)

class GettyKeyword(object):
    def __init__(self, id, text, type='Unknown', prominence=None):
        self.id = id
        self.text = text
        self.type = type
        self.prominence = prominence

    def __repr__(self):
        return '<%s %s[%s] "%s">' % (self.type, self.__class__.__name__, self.id, self.text)

    def __str__(self):
        return self.text

class GettyImage(object):
    def __init__(self, client, data):
        self.client = client

        self.id = data['ImageId']
        self.caption = data['Caption']
        self.title = data['Title']
        self.artist = data['Artist']

        self.variants = {
            'layout': GettyImageVariant(self, GETTY_VARIANT_LAYOUT, data['UrlComp']),
            'preview': GettyImageVariant(self, GETTY_VARIANT_PREVIEW, data['UrlPreview']),
            'thumbnail': GettyImageVariant(self, GETTY_VARIANT_THUMBNAIL, data['UrlThumb']),
            'watermark_layout': GettyImageVariant(self, GETTY_VARIANT_LAYOUT, data['UrlWatermarkComp'], watermark=True),
            'watermark_preview': GettyImageVariant(self, GETTY_VARIANT_PREVIEW, data['UrlWatermarkPreview'], watermark=True),
        }
        self.variants.update(dict(
            (v['SizeKey'],
            GettyImageVariant(
                self,
                '%dx%d' % (v['PixelWidth'], v['PixelHeight']),
                size=v['FileSizeInBytes'],
                dpi=v['ResolutionDpi'],
                id=v['SizeKey'],
                dimensions=(v['PixelWidth'], v['PixelHeight']),
                paid=True
            )) for v in data['SizesDownloadableImages']
        ))
        if len(data['SizesDownloadableImages']):
            self.variants['largest'] = GettyImageVariant(self, GETTY_VARIANT_LARGEST, paid=True)

        self.url = data['UrlComp']

        self.created = GettyImage.to_datetime(data['DateCreated'])
        self.published = GettyImage.to_datetime(data['DateSubmitted'])

        self.keywords = [GettyKeyword(
            kw['Id'], kw['Text'], type=kw.get('Type', 'Unknown'), prominence=kw.get('VisualProminence', None)
        ) for kw in data['Keywords']]

    @staticmethod
    def to_datetime(json_date):
        matches = match('/Date\(([0-9]+)\)\/', json_date)
        if matches:
            return datetime.fromtimestamp(int(matches.group(1)) // 1000, UTC)

        matches = match('/Date\(([0-9]+)([\-+])([0-9]{2})([0-9]{2})\)/', json_date)
        if matches:
            tz = FixedOffset(
                (int(matches.group(3).lstrip('0') or 0) * 60 + int(matches.group(4).strip('0') or 0))
                    * int('%s1' % matches.group(2))
            )
            return datetime.fromtimestamp(int(matches.group(1)) // 1000, tz=tz)

    def __str__(self):
        return self.url

    def __repr__(self):
        return '<%s[%s] "%s">' % (self.__class__.__name__, self.id, self.url)

class GettyCollection(list):
    def __init__(self, client, images):
        super(GettyCollection, self).__init__([
            GettyImage(client, image) for image in images
        ])
        self.paging = {}

    def get_meta(self):
        return self.paging or None
    def set_meta(self, search):
        self.paging = {
            'page': search['ItemStartNumber'],
            'total': search['ItemTotalCount'],
            'count': search['ItemCount'],
        }
    meta = property(get_meta, set_meta)
    page = property(lambda self: self.paging.get('page', None))
    total = property(lambda self: self.paging.get('total', None))
    count = property(lambda self: self.paging.get('count', None))

    def __repr__(self):
        return '<%s count=%d>' % (self.__class__.__name__, len(self))

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

    def __repr__(self):
        if self.activated:
            return '<%s expires at %s>' % (self.__class__.__name__, self.expires)
        return '<No%s>' % self.__class__.__name__

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

    def _normalize_count(self, count):
        counts = map(int, '1,2,3,4,5,6,10,12,15,20,25,30,50,60,75'.split(','))

        if count not in counts:
            try:
                return filter(lambda x: x > count, counts)[0]
            except IndexError:
                return counts[-1]

        return count

    def details(self, ids, language='en-us'):
        return GettyCollection(self, self._request(
            'http://connect.gettyimages.com/v1/search/GetImageDetails',
            GetImageDetailsRequestBody={
                'ImageIds': ids,
                'Language': language,
            }
        )['GetImageDetailsResult']['Images'] if ids else [])

    def search(self, query, count=10, page=1, **kwargs):
        _count, count = count, self._normalize_count(count)

        search = self._request(
            "http://connect.gettyimages.com/v1/search/SearchForImages",
            SearchForImages2RequestBody={
                'Filter': {
                    'LicensingModels': kwargs.get('licensing_models', ['RoyaltyFree']),
                    'FileTypes': kwargs.get('file_types', ['jpg']),
                    'ImageFamilies': kwargs.get('image_families', ['creative']),
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

        ids = [image['ImageId'] for image in search.pop('Images', [])]
        result = self.details(ids[:_count], language=kwargs.get('language', 'en-us'))
        result.meta = search

        return result

    def get_urls(self, *args):
        variants = []
        for arg in args:
            if isinstance(arg, (tuple, list, set)):
                variants += list(arg)
            else:
                variants.append(arg)

        sizes = [] # for GetImageDownloadAuthorizations request
        images = [] # for GetLargestImageDownloadAuthorizations request
        detail_ids = [] # for additional GetImageDetails request
        tokens = {} # for download tokens
        urls = {} # result

        for variant in variants:
            if isinstance(variant, GettyImageVariant):
                if variant.name in [GETTY_VARIANT_LAYOUT, GETTY_VARIANT_PREVIEW, GETTY_VARIANT_THUMBNAIL]:
                    urls[variant.owner.id] = variant.url
                    continue

                image = {'ImageId': variant.owner.id}
                if variant.name != GETTY_VARIANT_LARGEST:
                    image['SizeKey'] = variant.id
                    sizes.append(image)
                else:
                    images.append(image)
            elif isinstance(variant, GettyImage):
                urls[variant.id] = variant.url
            elif isinstance(variant, basestring):
                detail_ids.append(variant)
            else:
                raise GettyException('Can not gain url for unknown object type: %s' % type(variant))

        if detail_ids:
            for variant in self.details(detail_ids):
                urls[variant.id] = variant.url

        # Currently Getty API has an error in CreateDownloadRequest response. Each download token has only
        # SizeName parameter with None value, so we can't determine image size and response many sizes for one
        # image. So I temporary restrict this call. If you defined more than one dimension, I'll do only one
        # download url call for that image. If you specified "free" image variant, that does not required
        # download token I'll use it.
        sizes = filter(lambda v: v['ImageId'] not in urls, sizes)
        images = filter(lambda v: v['ImageId'] not in urls, images)

        if sizes:
            for image in self._request(
                'http://connect.gettyimages.com/v1/download/GetImageDownloadAuthorizations',
                GetImageDownloadAuthorizationsRequestBody={'ImageSizes': sizes}
            )['GetImageDownloadAuthorizationsResult']['Images']:
                tokens[image['ImageId']] = tokens.get(image['ImageId'], {})
                tokens[image['ImageId']][image['SizeKey']] = image['Authorizations'][0]['DownloadToken']

        if images:
            for image in self._request(
                'http://connect.gettyimages.com/v1/download/GetLargestImageDownloadAuthorizations',
                GetLargestImageDownloadAuthorizationsRequestBody={'Images': images}
            )['GetLargestImageDownloadAuthorizationsResult']['Images']:
                tokens[image['ImageId']] = tokens.get(image['ImageId'], {})
                tokens[image['ImageId']][image['Authorizations'][0]['SizeKey']] = image['Authorizations'][0]['DownloadToken']

        if tokens:
            items = []
            for data in tokens.values():
                items.extend({'DownloadToken': token} for token in data.values()[:1])
            print items

            for image in self._request(
                'https://connect.gettyimages.com/v1/download/CreateDownloadRequest',
                CreateDownloadRequestBody={'DownloadItems': items}
            )['CreateDownloadRequestResult']['DownloadUrls']:
                urls[image['ImageId']] = image['UrlAttachment']

        return urls

    def __repr__(self):
        return '<%s[%s] for %s>' % (self.__class__.__name__, self.system_id, self.user_name)

if __name__ == '__main__':
    gc = GettyClient('xxxxx', '0123456789abcdefghijklmnopqrstuvwxyz01234567', 'username', 'passwordhash')
    print gc.search('propaganda', count=1)
