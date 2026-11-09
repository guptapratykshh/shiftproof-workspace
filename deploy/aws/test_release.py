"""Validate release address selection without contacting AWS or DNS."""
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from release import PUBLIC_URL_PARAMETER, public_url


class PublicAddressTests(unittest.TestCase):
    def setUp(self):
        class ParameterNotFound(Exception):
            pass
        self.ssm = Mock()
        self.ssm.exceptions = SimpleNamespace(ParameterNotFound=ParameterNotFound)
        self.fallback = 'https://13.203.164.49'
        self.domain = 'https://shiftproof.duckdns.org'
        self.dns = patch('release.socket.gethostbyname_ex', return_value=(
            'shiftproof.duckdns.org', [], ['13.203.164.49']))
        self.dns.start()
        self.addCleanup(self.dns.stop)

    def test_existing_hostname_survives_later_releases(self):
        self.ssm.get_parameter.return_value = {'Parameter': {'Value': self.domain}}
        self.assertEqual(public_url(self.ssm, None, self.fallback), self.domain)
        self.ssm.get_parameter.assert_called_once_with(Name=PUBLIC_URL_PARAMETER)

    def test_first_release_uses_stack_address(self):
        self.ssm.get_parameter.side_effect = self.ssm.exceptions.ParameterNotFound()
        self.assertEqual(public_url(self.ssm, None, self.fallback), self.fallback)

    def test_explicit_hostname_takes_precedence(self):
        self.assertEqual(public_url(self.ssm, self.domain + '/', self.fallback), self.domain)
        self.ssm.get_parameter.assert_not_called()

    def test_permission_failure_does_not_silently_restore_ip(self):
        self.ssm.get_parameter.side_effect = PermissionError('Access denied')
        with self.assertRaises(PermissionError):
            public_url(self.ssm, None, self.fallback)

    def test_non_origin_inputs_rejected(self):
        for value in ('http://shiftproof.duckdns.org', self.domain + ':443',
                      self.domain + '/signup', self.domain + '?query=x',
                      self.domain + '#fragment', 'https://user@shiftproof.duckdns.org',
                      'https://shiftproof.duckdns.org\nother'):
            with self.subTest(value=value), self.assertRaises(ValueError):
                public_url(self.ssm, value, self.fallback)

    def test_hostname_cannot_point_to_another_server(self):
        for addresses in (['192.0.2.1'], ['13.203.164.49', '192.0.2.1'], []):
            with self.subTest(addresses=addresses), patch(
                'release.socket.gethostbyname_ex', return_value=('example.org', [], addresses)
            ), self.assertRaises(ValueError):
                public_url(self.ssm, self.domain, self.fallback)


if __name__ == '__main__':
    unittest.main()
