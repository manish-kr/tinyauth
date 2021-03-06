import base64
import contextlib
import json
import os
import unittest
from unittest import mock

from tinyauth.app import create_app, db
from tinyauth.models import AccessKey, User, UserPolicy


class BaseTestCase(unittest.TestCase):

    backend = None

    def patch(self, *args, **kwargs):
        patcher = mock.patch(*args, **kwargs)
        self.addCleanup(patcher.stop)
        return patcher.start()

    def patch_object(self, *args, **kwargs):
        patcher = mock.patch.object(*args, **kwargs)
        self.addCleanup(patcher.stop)
        return patcher.start()

    def patch_dict(self, *args, **kwargs):
        patcher = mock.patch.dict(*args, **kwargs)
        self.addCleanup(patcher.stop)
        return patcher.start()

    def setUp(self):
        self.stack = contextlib.ExitStack()

        self.app = create_app(self)
        self.app.config['WTF_CSRF_ENABLED'] = False
        self.client = self.app.test_client()

        self._ctx = self.app.test_request_context()
        self._ctx.push()

        uuid4 = self.stack.enter_context(mock.patch('uuid.uuid4'))
        uuid4.return_value = 'a823a206-95a0-4666-b464-93b9f0606d7b'

        self.audit_log = self.stack.enter_context(mock.patch('tinyauth.audit.logger.info'))

        self.backend = self.backend or self.app

    def tearDown(self):
        self._ctx.pop()
        self.stack.close()
        super().tearDown()

    def req(self, method, uri, headers=None, body=None):
        actual_headers = {
            'Authorization': 'Basic {}'.format(
                base64.b64encode(b'AKIDEXAMPLE:password').decode('utf-8')
            ),
        }
        if headers:
            actual_headers.update(headers)

        method = getattr(self.client, method)

        return method(
            uri,
            headers=actual_headers,
            content_type='application/json',
            data=json.dumps(body) if body else None,
        )


class TestCase(BaseTestCase):

    def setUp(self):
        super().setUp()
        self.setup_db(self.app)

    def setup_db(self, app):
        app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
        db.create_all(app=app)

        self.user = user = User(username='charles')
        user.set_password('mrfluffy')
        db.session.add(user)

        policy = UserPolicy(name='tinyauth', user=user, policy={
            'Version': '2012-10-17',
            'Statement': [{
                'Action': 'tinyauth:*',
                'Resource': 'arn:tinyauth:*',
                'Effect': 'Allow',
            }]
        })
        db.session.add(policy)

        access_key = AccessKey(
            access_key_id='AKIDEXAMPLE',
            secret_access_key='password',
            user=user,
        )
        db.session.add(access_key)

        self.user2 = user = User(username='freddy')
        user.set_password('mrfluffy2')
        db.session.add(user)

        db.session.add(AccessKey(
            access_key_id='AKIDEXAMPLE2',
            secret_access_key='password',
            user=user,
        ))

        db.session.commit()

    def tearDown(self):
        with self.backend.app_context():
            db.session.remove()
            db.drop_all()
        super().tearDown()


class TestProxyMixin(object):

    def setUp(self):
        self.backend = create_app(None)
        with self.backend.app_context():
            self.setup_db(self.backend)

        self.stack = contextlib.ExitStack()

        environ = {
            'TINYAUTH_ENDPOINT': 'http://localhost',
            'TINYAUTH_ACCESS_KEY_ID': 'AKIDEXAMPLE',
            'TINYAUTH_SECRET_ACCESS_KEY': 'password',
            'TINYAUTH_AUTH_MODE': 'proxy',
        }

        with mock.patch.dict(os.environ, environ):
            self.app = create_app(self)
            self.app.config['WTF_CSRF_ENABLED'] = False
            self.session = self.stack.enter_context(mock.patch.object(self.app.auth_backend, 'session'))

        self.client = self.app.test_client()

        self._ctx = self.app.test_request_context()
        self._ctx.push()

        uuid4 = self.stack.enter_context(mock.patch('uuid.uuid4'))
        uuid4.return_value = 'a823a206-95a0-4666-b464-93b9f0606d7b'

        self.audit_log = self.stack.enter_context(mock.patch('tinyauth.audit.logger.info'))

        def session_get(url, headers, auth, verify):
            with self.backend.app_context():
                with self.backend.test_client() as client:
                    r = client.get(
                        url,
                        headers={
                            'Authorization': 'Basic {}'.format(
                                base64.b64encode(b'AKIDEXAMPLE:password').decode('utf-8')
                            )
                        },
                        content_type='application/json',
                    )

                response = mock.Mock()
                response.headers = dict(r.headers)
                response.status_code = r.status_code
                response.json.return_value = json.loads(r.get_data(as_text=True))
                return response

        self.session.get.side_effect = session_get
