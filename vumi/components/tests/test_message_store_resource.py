# -*- coding: utf-8 -*-

import json

from twisted.internet import reactor
from twisted.internet.defer import inlineCallbacks
from twisted.web.server import Site

from vumi.utils import http_request_full

from vumi.tests.helpers import (
    VumiTestCase, MessageHelper, PersistenceHelper, import_skip,
)


class TestMessageStoreResource(VumiTestCase):

    timeout = 1

    @inlineCallbacks
    def setUp(self):
        self.persistence_helper = self.add_helper(
            PersistenceHelper(use_riak=True))
        try:
            from vumi.components.message_store import MessageStore
            from vumi.components.message_store_resource import (
                MessageStoreResource)
        except ImportError, e:
            import_skip(e, 'riakasaurus', 'riakasaurus.riak')
        self.redis = yield self.persistence_helper.get_redis_manager()
        self.manager = self.persistence_helper.get_riak_manager()
        self.store = MessageStore(self.manager, self.redis)
        self.store_resource = MessageStoreResource(self.store)
        self.msg_helper = self.add_helper(MessageHelper())
        self.site = Site(self.store_resource)
        port = reactor.listenTCP(0, self.site)
        addr = port.getHost()
        self.addCleanup(self.stop_server, port)
        self.url = 'http://%s:%s' % (addr.host, addr.port)

    def stop_server(self, port):
        d = port.stopListening()
        d.addCallback(lambda _: port.loseConnection())
        return d

    def make_batch(self, tag):
        return self.store.batch_start([tag])

    def make_outbound(self, batch_id, content):
        msg = self.msg_helper.make_outbound(content)
        d = self.store.add_outbound_message(msg, batch_id=batch_id)
        d.addCallback(lambda _: msg)
        return d

    def make_inbound(self, batch_id, content):
        msg = self.msg_helper.make_inbound(content)
        d = self.store.add_inbound_message(msg, batch_id=batch_id)
        d.addCallback(lambda _: msg)
        return d

    def make_request(self, method, batch_id, leaf):
        url = '%s/%s/%s' % (self.url, batch_id, leaf)
        return http_request_full(method=method, url=url)

    def get_batch_resource(self, batch_id):
        return self.store_resource.getChild(batch_id, None)

    @inlineCallbacks
    def test_get_inbound(self):
        batch_id = yield self.make_batch(('foo', 'bar'))
        msg1 = yield self.make_inbound(batch_id, 'føø')
        msg2 = yield self.make_inbound(batch_id, 'føø')
        resp = yield self.make_request('GET', batch_id, 'inbound.json')
        messages = map(
            json.loads, filter(None, resp.delivered_body.split('\n')))
        self.assertEqual(
            set([msg['message_id'] for msg in messages]),
            set([msg1['message_id'], msg2['message_id']]))

    @inlineCallbacks
    def test_get_outbound(self):
        batch_id = yield self.make_batch(('foo', 'bar'))
        msg1 = yield self.make_outbound(batch_id, 'føø')
        msg2 = yield self.make_outbound(batch_id, 'føø')
        resp = yield self.make_request('GET', batch_id, 'outbound.json')
        messages = map(
            json.loads, filter(None, resp.delivered_body.split('\n')))
        self.assertEqual(
            set([msg['message_id'] for msg in messages]),
            set([msg1['message_id'], msg2['message_id']]))
