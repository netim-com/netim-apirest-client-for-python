import time
from APIRest import APIRest

sld = 'client-rest-php-'
tld = 'xyz'
index = 2

api = APIRest('NETIM', 'q2cp$8rjn')

# Hello
print('hello : ')
response = api.hello()
print(response)

# Domain registration
print('domainCreate : ')
response = api.domainCreate(
	sld + str(++index) + '.' + tld,
	'SN617',
	'SN616',
	'SN616',
	'SN616',
	{
		1: {'name': 'ns1-dev.netim.net'},
		2: {'name': 'ns2-dev.netim.net'},
	},
	1,
)
print(response)
time.sleep(5)

# Domain change DNS
print('domainChangeDNS : ')
response = api.domainChangeDNS(
	sld + str(++index) + '.' + tld,
	{
		1: {'name': 'ns1-nonameservers.netim.net'},
		2: {'name': 'ns2-nonameservers.netim.net'},
	}
)
print(response)
time.sleep(5)

"""


# Contact change
print('domainChangeContact : ')
response = api.domainChangeContact(
	domain,
	'SN616',
	'SN616',
	'SN616',
	{
		'local': True,
	}
)
print(response)
time.sleep(5)

print('domainChangeContact : ')
response = api.domainChangeContact(
	domain,
	'SN616',
	'SN616',
	'SN616'
)
print(response)
time.sleep(5)


# Change owner
print('domainTransferOwner : ')
response = api.domainTransferOwner(
	domain,
	'SN844'	
)
print(response) """

print('domainTransferOwner : ')
response = api.domainTransferOwner(
	domain,
	'SN844',
	{
		'trustee': True,
		'intendedUse': 'Pouet pouet tralala',
	}
)
print(response)