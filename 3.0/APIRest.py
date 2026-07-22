#!/usr/bin/python3
# coding: utf-8

import json
import requests
import atexit
from lxml import etree
import os
from NetimAPIException import *


class APIRest:
    """Constructor for class APIRest

    Args:
        name (str): API user name
        key (str): API key

    """

    __connected = False
    __sessionID = None

    __name = None
    __key = None
    __apiURL = None
    __preferences = {"lang": None}

    __lastRequestParams = None
    __lastRequestRessource = None
    __lastHttpVerb = None
    __lastHttpStatus = None
    __lastResponse = None
    __lastError = None

    def __init__(self, name: str = None, key: str = None):
        atexit.register(self.__del__)

        xml = etree.parse(os.path.dirname(os.path.abspath(__file__)) + "/conf.xml")
        try:
            if name is None and key is None:  # No parameters
                if (
                    xml.xpath("/configuration/name")[0].text != ""
                    and xml.xpath("/configuration/key")[0].text != ""
                ):
                    self.__name = xml.xpath("/configuration/name")[0].text
                    self.__key = xml.xpath("/configuration/key")[0].text
                else:
                    raise NetimAPIException("Missing login/key in conf file.")
            elif name is not None and key is not None:  # With parameters
                self.__name = name
                self.__key = key
            else:
                raise NetimAPIException("Missing name/key.")

            if xml.xpath("/configuration/url")[0].text != "":
                self.__apiURL = xml.xpath("/configuration/url")[0].text
            else:
                raise NetimAPIException("Missing URL in conf file.")

            perfs = xml.xpath("/configuration/preferences")[0]
            for item in perfs:
                if item.text:
                    self.__preferences[item.tag] = item.text

            if not self.__preferences.get("lang"):
                self.__preferences["lang"] = "EN"

        except IndexError:
            raise NetimAPIException("Missing parameter in conf.xml")

    def __del__(self):
        if self.__connected and self.__sessionID is not None:
            self.sessionClose()

    def __isSessionOpen(self, ressource: str, httpVerb: str):
        return "session" in ressource and httpVerb == "post"

    def __isSessionClose(self, ressource: str, httpVerb: str):
        return "session" in ressource and httpVerb == "delete"

    def call(self, ressource: str, httpVerb: str, params: dict = {}):
        """Launches a function of the API, abstracting the connect/disconnect part to one place

        Example 1: API command returning a StructOperationResponse

        return self.call("contacts/$idContactToDelete", {}, 'delete');

        Example 2: API command that takes many args
        params = {
            'host': host,
            'ipv4': ipv4,
            'ipv6': ipv6
        }
        return $this->call('/hosts', params, 'post');


        Args:
            ressource (str): name of a ressource in the API.
            params (dict): the parameters of ressource.
            httpVerb (str): the http verb for the request (get, post, put, patch, delete).

        Raises:
            NetimAPIException: if httpverb is wrong or an error described in the exception's message.

        Returns:
            dict: the result of the call of ressource with parameters param and http verb httpVerb.
        """
        httpVerb = httpVerb.lower()
        ressource = ressource.lstrip("/")
        self.__lastRequestRessource = ressource
        self.__lastRequestParams = params
        self.__lastHttpVerb = httpVerb
        self.__lastHttpStatus = ""
        self.__lastResponse = ""
        self.__lastError = ""

        try:
            # login
            if not self.__connected:
                if self.__isSessionClose(ressource, httpVerb):
                    return
                elif not self.__isSessionOpen(ressource, httpVerb):
                    self.sessionOpen()
            elif self.__connected and self.__isSessionOpen(ressource, httpVerb):
                return

            # Call the REST ressource
            if self.__isSessionOpen(ressource, httpVerb):
                headers = {
                    "Accept-Language": self.__preferences["lang"],
                    "Content-Type": "application/json",
                }
                response = requests.post(
                    self.__apiURL + "/session",
                    auth=(self.__name, self.__key),
                    headers=headers,
                    data=json.dumps({"preferences": self.__preferences}),
                )
                
            else:
                headers = {
                    "Authorization": "Bearer " + self.__sessionID,
                    "Content-type": "application/json",
                }
                function = getattr(requests, httpVerb)

                if params:
                    response = function(
                        self.__apiURL + "/" + ressource,
                        headers=headers,
                        data=json.dumps(params),
                    )
                else:
                    response = function(
                        self.__apiURL + "/" + ressource,
                        headers=headers,
                    )

            self.__lastHttpStatus = response.status_code

            try:
                result = json.loads(response.text)
            except json.decoder.JSONDecodeError:
                raise NetimAPIException("Unknown error")

            if self.__isSessionClose(ressource, httpVerb):
                # 401 means the session already expired: consider it closed
                if response.status_code in (200, 401):
                    self.__sessionID = None
                    self.__connected = False
                else:
                    raise NetimAPIException(
                        result.get("message", "HTTP " + str(response.status_code))
                    )
            elif self.__isSessionOpen(ressource, httpVerb):
                if response.status_code == 200:
                    self.__sessionID = result["access_token"]
                    self.__connected = True
                else:
                    raise NetimAPIException(
                        result.get("message", "HTTP " + str(response.status_code))
                    )
            else:
                # Code doesn't start with "2xx"
                if response.status_code < 200 or response.status_code > 299:
                    if response.status_code == 401:
                        self.__sessionID = None
                        self.__connected = False
                    if "message" in result:
                        raise NetimAPIException(result["message"])
                    else:
                        raise NetimAPIException("HTTP " + str(response.status_code))

            self.__lastResponse = result
        except NetimAPIException as exception:
            self.__lastError = str(exception)
            raise exception

        return result

    """
    GETTER
    """

    def getLastRequestParams(self):
        return self.__lastRequestParams

    def getLastRequestRessource(self):
        return self.__lastRequestRessource

    def getLastHttpVerb(self):
        return self.__lastHttpVerb

    def getLastHttpStatus(self):
        return self.__lastHttpStatus

    def getLastResponse(self):
        return self.__lastResponse

    def getLastError(self):
        return self.__lastError

    """
    API FUNCTIONS
    """

    def sessionOpen(self) -> None:
        """Opens a session with REST

        Raises:
            NetimAPIException: if failed to connect.
        """
        self.call("session", "post")

    def sessionClose(self) -> None:
        if self.__connected and self.__sessionID is not None:
            # call() resets __sessionID/__connected on 200 and 401,
            # and raises NetimAPIException on any other status
            self.call("session", "delete")
        self.__connected = False

    def sessionInfo(self) -> dict:
        """Return the information of the current session.

        Raises:
            NetimAPIException: if user is not connected.

        Returns:
            dict: A structure StructSessionInfo

        See:
            sessionInfo API https://support.netim.com/en/wiki/SessionInfo

        """
        if not self.__connected:
            raise NetimAPIException("Not connected")
        return self.call("session/", "get")

    def queryAllSessions(self) -> list:
        """Returns all active sessions linked to the reseller account.

        Returns:
            dict: a dictionary of StructSessionInfo.

        See:
            queryAllSessions API https://support.netim.com/en/wiki/QueryAllSessions
        """
        return self.call("sessions/", "get")

    def sessionSetPreference(self, type: str, value: str) -> None:
        """Updates the settings of the current session.

        Args:
            type (str): Setting to be modified ('lang','sync')
            value (str): New value of the Setting (lang: 'EN';'FR',sync:'0'(for asynchronous);'1'(for synchronous)).
        """
        self.call("session/", "patch", {"preferences": {type: value}})

    def hello(self) -> str:
        """Returns a welcome message

                Raises:
            NetimAPIException:

        Returns:
            str: string a welcome message

        See:
            hello API http://support.netim.com/en/wiki/Hello
        """

        return self.call("hello/", "get")

    def accountInfo(self) -> dict:
        """Returns the list of parameters reseller account

        Returns:
            str: list of parameters reseller account
        """
        return self.call("account/", "get")

    def contactCreate(self, contact: dict) -> dict:
        """Creates a contact

        Args:
            contact (Contact): the contact to create

        Returns:
            str: the ID of the contact

        See:
            contactCreate API http://support.netim.com/en/wiki/ContactCreate
            StructContact: http://support.netim.com/en/wiki/StructContact
        """

        params = {"contact": contact}
        return self.call("contact/", "post", params)

    def contactInfo(self, id: str) -> dict:
        """Returns all informations about a contact object

        Args:
            id (str): ID of the contact to be queried

        Returns:
            Contact: information on the contact
        See:
            contactInfo API http://support.netim.com/en/wiki/ContactInfo
            StructContactReturn API http://support.netim.com/en/wiki/StructContactReturn
        """

        return self.call("contact/" + id, "get")

    def contactUpdate(self, id: str, contact: dict) -> dict:
        """Edit contact details

        Args:
            id (str): the ID of the contact to be updated
            contact (Contact): the contact object containing the new values

        Returns:
            StructOperationResponse: giving information on the status of the operation

        Throws:
            NetimAPIException

        See:
            contactUpdate API http://support.netim.com/en/wiki/ContactUpdate
        """

        params = {"contact": contact}
        return self.call("contact/" + id, "patch", params)

    def contactDelete(self, id: str) -> dict:
        """Deletes a contact object

        Args:
            id (str): ID of the contact to be deleted

        Returns:
            StructOperationResponse: giving information on the status of the operation

        Throws:
            NetimAPIException

        See:
            contactDelete API http://support.netim.com/en/wiki/ContactDelete
            StructOperationResponse API http://support.netim.com/en/wiki/StructOperationResponse
        """

        return self.call("contact/" + id, "delete")

    def opeInfo(self, id: str) -> dict:
        """Query informations about the state of an operation

        Args:
            id (str): The id of the operation requested

        Returns:
            StructOperationResponse: giving information on the status of the operation

        Throws:
            NetimAPIException

        See:
            opeInfo API http://support.netim.com/en/wiki/opeInfo
        """

        return self.call("operation/" + id, "get")

    def cancelOpe(self, id: str) -> None:
        """Cancel a pending operation

        Warning:
            Depending on the current status of the operation, the cancellation might not be possible

        Args:
            id (str): Tracking ID of the operation

        Throws:
            NetimAPIException

        See:
            cancelOpe http://support.netim.com/en/wiki/CancelOpe
        """

        self.call("operation/" + id + "/cancel/", "patch")

    def opeList(self, filters: dict) -> list:
        """Returns the status (opened/closed) for all operations for the extension

        Args:
            tld (str): Extension (uppercase without dot)

        Returns:
            dict: A dictionary with (Name of the operation, boolean active)

        Throws:
            NetimAPIException

        See:
            queryOpeList API https://support.netim.com/en/wiki/QueryOpeList
        """

        params = {"filters": filters}
        return self.call("operations/", "post", params)

    def contactList(self, filters: dict) -> list:
        """Returns all contacts linked to the reseller account.

        Args:
            filter (str): The filter applies on the "field"
            field (str): idContact / firstName / lastName / bodyForm / isOwner

        Returns:
            StructContactList[]: An array of StructContactList

        Throws:
            NetimAPIException

        See:
            contactList API https://support.netim.com/en/wiki/contactList
        """

        params = {"filters": filters}
        return self.call("contacts/", "post", params)

    def hostCreate(self, host: str, ipv4: list, ipv6: list) -> dict:
        """Creates a new host at the registry

        Args:
            host (str): hostname
            ipv4 (list): Must contain ipv4 adresses as strings
            ipv6 (list): Must contain ipv6 adresses as strings

        Returns:
            StructOperationResponse: giving information on the status of the operation

        Throws:
            NetimAPIException

        See:
            hostCreate API https://support.netim.com/en/wiki/HostCreate
        """
        params = {
            "host": host,
            "ipv4": ipv4,
            "ipv6": ipv6,
        }
        return self.call("host/", "post", params)

    def hostInfo(self, host: str) -> dict:
        """Returns all informations about a host object

        Args:
            host (str): Name of the host to be queried

        Returns:
            Host informations
        """

        return self.call("host/" + host, "get")

    def hostDelete(self, host: str) -> dict:
        """Deletes an Host at the registry

        Args:
            host (str): hostname to be deleted

        Returns:
            StructOperationResponse: giving information on the status of the operation

        Throws:
            NetimAPIException

        See:
            hostDelete API https://support.netim.com/en/wiki/HostDelete
        """
        return self.call("host/" + host, "delete")

    def hostUpdate(self, host: str, ipv4: list, ipv6: list) -> dict:
        """Updates a host at the registry

        Args:
            host (str): hostname
            ipv4 (list): Must contain ipv4 adresses as strings
            ipv6 (list): Must contain ipv6 adresses as strings

        Returns:
            StructOperationResponse: giving information on the status of the operation

        Throws:
            NetimAPIException

        See:
            hostUpdate API http://support.netim.com/en/wiki/HostUpdate
        """
        params = {
            "ipv4": ipv4,
            "ipv6": ipv6,
        }
        return self.call("host/" + host, "patch", params)

    def hostList(self, filters: dict) -> list:
        """Returns all hosts linked to the reseller account.

        Args:
            filters (dict): The filter applies onto the host name

        Returns:
            StructHostList[]: a list of StructHostList

        Throws:
            NetimAPIException

        See:
            hostList API http://support.netim.com/en/wiki/hostList
        """

        params = {"filters": filters}
        return self.call("hosts/", "post", params)

    def domainCheck(self, domain: str) -> list:
        """Checks if domain names are available for registration

        Args:
            domain (str): Domain names to be checked
                                You can provide several domain names separated with semicolons.
                        Caution :
                            - you can't mix different extensions during the same call
                            - all the extensions don't accept a multiple checkDomain. See HasMultipleCheck in Category:Tld
        Returns:
            StructDomainCheckResponse[]: a list of StructDomainCheckResponse
        Throws:
            NetimAPIException
        See:
            DomainCheck API http://support.netim.com/en/wiki/DomainCheck
            StructDomainCheckResponse http://support.netim.com/en/wiki/StructDomainCheckResponse
        """

        domain = domain.lower()

        return self.call("domain/" + domain + "/check/", "get")

    def domainCreate(
        self,
        domain: str,
        idOwner: str,
        idAdmin: str,
        idTech: str,
        idBilling: str,
        nameservers: dict,
        duration: int,
        options: dict = None,
    ) -> dict:
        """Requests a new domain registration

        Args:
            domain (str): the name of the domain to create
            idOwner (str): the id of the owner for the new domain
            idAdmin (str): the id of the admin for the new domain
            idTech (str): the id of the tech for the new domain
            idBilling (str): the id of the billing for the new domain
            nameservers (dict): the list of nameservers
            duration (int): how long the domain will be created
            options (dict): additional options for the domain creation

        Returns:
            StructOperationResponse: giving information on the status of the operation

        Throws:
            NetimAPIException

        See:
            domainCreate API http://support.netim.com/en/wiki/DomainCreate
        """
        domain = domain.lower()

        params = {
            "idOwner": idOwner,
            "idAdmin": idAdmin,
            "idTech": idTech,
            "idBilling": idBilling,
            "nameservers": nameservers,
            "duration": duration,
        }

        if options is not None:
            params["options"] = options

        return self.call("domain/" + domain + "/", "post", params)

    def domainInfo(self, domain: str) -> dict:
        """Returns all informations about a domain name

        Args:
            domain (str): name of the domain

        Returns:
            StructDomainInfo: information about the domain

        See:
            domainInfo API http://support.netim.com/en/wiki/DomainInfo
        """

        domain = domain.lower()

        return self.call("domain/" + domain + "/info/", "get")

    def domainCreateLP(
        self,
        domain: str,
        idOwner: str,
        idAdmin: str,
        idTech: str,
        idBilling: str,
        nameservers: dict,
        duration: int,
        launchPhase: str,
    ) -> dict:
        """Requests a new domain registration

        Args:
            domain (str): the name of the domain to create
            idOwner (str): the id of the owner for the new domain
            idAdmin (str): the id of the admin for the new domain
            idTech (str): the id of the tech for the new domain
            idBilling (str): the id of the billing for the new domain
            nameservers (dict): the list of nameservers
            duration (int): how long the domain will be created
            launchPhase (str): Code of the launch period.

        Returns:
            StructOperationResponse: giving information on the status of the operation

        Throws:
            NetimAPIException

        See:
            domainCreate API http://support.netim.com/en/wiki/DomainCreateLP
        """
        domain = domain.lower()

        params = {
            "idOwner": idOwner,
            "idAdmin": idAdmin,
            "idTech": idTech,
            "idBilling": idBilling,
            "nameservers": nameservers,
            "duration": duration,
            "launchPhase": launchPhase,
        }

        return self.call("domain/" + domain + "/lp/", "post", params)

    def domainDelete(self, domain: str, typeDelete: str = "NOW") -> dict:
        """Deletes immediately a domain name

        Args:
            domain (str): the name of the domain to delete
            typeDelete (str, optional): if the deletion is to be done now or not. Only supported value as of 2.0 is 'NOW'. Defaults to 'NOW'.

        Returns:
            StructOperationResponse: giving information on the status of the operation

        Throws:
            NetimAPIException

        See:
            domainDelete API http://support.netim.com/en/wiki/DomainDelete
        """

        domain = domain.lower()

        params = {"typeDelete": typeDelete.upper()}

        return self.call("domain/" + domain + "/", "delete", params)

    def domainTransferIn(
        self,
        domain: str,
        authID: str,
        idOwner: str,
        idAdmin: str,
        idTech: str,
        idBilling: str,
        nameservers: dict,
        options: dict = None,
    ) -> dict:
        """Requests the transfer of a domain name to Netim

        Args:
            domain (str): name of the domain to transfer
            authID (str): authorisation code / EPP code (if applicable)
            idOwner (str): a valid idOwner. Can also be #AUTO#
            idAdmin (str): a valid idAdmin
            idTech (str): a valid idTech
            idBilling (str): a valid idBilling
            nameservers (dict): the list of nameservers
            options (dict, optional): additional options for the domain transfer

        Throws:
            NetimAPIException

        See:
            domainTransferIn API http://support.netim.com/en/wiki/DomainTransferIn

        Returns:
            StructOperationResponse: giving information on the status of the operation
        """

        domain = domain.lower()

        params = {
            "authID": authID,
            "idOwner": idOwner,
            "idAdmin": idAdmin,
            "idTech": idTech,
            "idBilling": idBilling,
            "nameservers": nameservers,
        }

        if options is not None:
            params["options"] = options

        return self.call("domain/" + domain + "/transfer/", "post", params)

    def domainTransferTrade(
        self,
        domain: str,
        authID: str,
        idOwner: str,
        idAdmin: str,
        idTech: str,
        idBilling: str,
        nameservers: dict,
        options: dict = None,
    ) -> dict:
        """Requests the transfer (with change of domain holder) of a domain name to Netim

        Args:
            domain (str): name of the domain to transfer
            authID (str): authorisation code / EPP code (if applicable)
            idOwner (str): a valid idOwner
            idAdmin (str): a valid idAdmin
            idTech (str): a valid idTech
            idBilling (str): a valid idBilling
            nameservers (dict): the list of nameservers
            options (dict, optional): additional options for the domain transfer

        Throws:
            NetimAPIException

        See:
            domainTransferIn API http://support.netim.com/en/wiki/DomainTransferTrade

        Returns:
            StructOperationResponse: giving information on the status of the operation
        """

        domain = domain.lower()

        params = {
            "authID": authID,
            "idOwner": idOwner,
            "idAdmin": idAdmin,
            "idTech": idTech,
            "idBilling": idBilling,
            "nameservers": nameservers,
        }
        
        if options is not None:
            params["options"] = options

        return self.call("domain/" + domain + "/transfer-trade/", "post", params)

    def domainInternalTransfer(
        self,
        domain: str,
        authID: str,
        idAdmin: str,
        idTech: str,
        idBilling: str,
        nameservers: dict,
        options: dict = None,
    ) -> dict:
        """Requests the internal transfer of a domain name from one Netim account to another

        Args:
            domain (str): name of the domain to transfer
            authID (str): authorisation code / EPP code (if applicable)
            idAdmin (str): a valid idAdmin
            idTech (str): a valid idTech
            idBilling (str): a valid idBilling
            nameservers (dict): the list of nameservers
            options (dict, optional): additional options:
                - type (str): "push" or "pull" (default "pull")
                - recipient (str): ID of the recipient account (mandatory when type is "push")

        Throws:
            NetimAPIException

        See:
            domainInternalTransfer API http://support.netim.com/en/wiki/DomainInternalTransfer

        Returns:
            StructOperationResponse: giving information on the status of the operation
        """
        domain = domain.lower()

        params = {
            "authID": authID,
            "idAdmin": idAdmin,
            "idTech": idTech,
            "idBilling": idBilling,
            "nameservers": nameservers,
        }

        if options is not None:
            params["options"] = options

        return self.call("domain/" + domain + "/internal-transfer/", "patch", params)

    def domainRenew(self, domain: str, duration: int) -> dict:
        """Renew a domain name for a new subscription period

        Args:
            domain (str): the name of the domain to renew
            duration (int): the duration of the renewal expressed in year. Must be at least 1 and less than the maximum amount

        Throws:
            NetimAPIException

        Returns:
            StructOperationResponse: giving information on the status of the operation

        See:
            domainRenew API  http://support.netim.com/en/wiki/DomainRenew
        """
        domain = domain.lower()
        params = {"duration": duration}

        return self.call("domain/" + domain + "/renew/", "patch", params)

    def domainRestore(self, domain: str) -> dict:
        """Restores a domain name in quarantine / redemption status

        Args:
            domain (str): name of the domain

        Throws:
            NetimAPIException

        Returns:
            StructOperationResponse: giving information on the status of the operation

        See:
            domainRenew API  http://support.netim.com/en/wiki/DomainRenew
        """
        domain = domain.lower()
        return self.call("domain/" + domain + "/restore/", "patch")

    def domainSetPreference(self, domain: str, codePref: str, value: str) -> dict:
        """Updates the settings of a domain name

        Args:
            domain (str): name of the domain
            codePref (str): setting to be modified. Accepted value are 'whois_privacy', 'registrar_lock', 'auto_renew', 'tag' or 'note'
            value (str): new value for the settings.

        Throws:
            NetimAPIException

        Returns:
            StructOperationResponse: giving information on the status of the operation

        See:
            domainSetPreference API  http://support.netim.com/en/wiki/DomainSetPreference
        """
        domain = domain.lower()

        params = {"codePref": codePref, "value": value}

        return self.call("domain/" + domain + "/preference/", "patch", params)

    def domainTransferOwner(self, domain: str, idOwner: str, options: dict = None) -> dict:
        """Requests the transfer of the ownership to another party

        Args:
            domain (str): name of the domain
            idOwner (str): id of the new owner

        Throws:
            NetimAPIException

        Returns:
            StructOperationResponse: giving information on the status of the operation

        See:
            domainTransferOwner API http://support.netim.com/en/wiki/DomainTransferOwner
        """
        domain = domain.lower()

        params = {"idOwner": idOwner}
        
        if options is not None:
            params["options"] = options

        return self.call("domain/" + domain + "/transfer-owner/", "put", params)

    def domainChangeContact(
        self, domain: str, idAdmin: str, idTech: str, idBilling: str, options: dict = None
    ) -> dict:
        """Replaces the contacts of the domain (administrative, technical, billing)

        Args:
            domain (str): name of the domain
            idAdmin (str):  id of the admin contact
            idTech (str):  id of the tech contact
            idBilling (str):  id of the billing contact

        Throws:
            NetimAPIException

        Returns:
            StructOperationResponse: giving information on the status of the operation

        See:
            domainChangeContact API http://support.netim.com/en/wiki/DomainChangeContact
        """
        domain = domain.lower()

        params = {"idAdmin": idAdmin, "idTech": idTech, "idBilling": idBilling}

        if options is not None:
            params["options"] = options

        return self.call("domain/" + domain + "/contacts/", "put", params)

    def domainChangeDNS(
        self, domain: str, nameservers: dict
    ) -> dict:
        """Replaces the DNS servers of the domain (redelegation)

        Args:
            domain (str): name of the domain
            nameservers (dict): the list of nameservers

        Throws:
            NetimAPIException

        Returns:
            StructOperationResponse: giving information on the status of the operation

        See:
            domainChangeDNS API http://support.netim.com/en/wiki/DomainChangeDNS
        """
        domain = domain.lower()

        params = {"nameservers": nameservers}

        return self.call("domain/" + domain + "/dns/", "put", params)

    def domainSetDNSSec(self, domain: str, enable: int) -> dict:
        """Allows to sign a domain name with DNSSEC if it uses NETIM DNS servers

        Args:
            domain (str): name of the domain
            enable (int): New signature value 0 : unsign 1 : sign

        Throws:
            NetimAPIException

        Returns:
            StructOperationResponse: giving information on the status of the operation

        See:
            domainSetDNSsec API http://support.netim.com/en/wiki/DomainSetDNSsec
        """
        domain = domain.lower()
        params = {"enable": enable}
        return self.call("domain/" + domain + "/dnssec/", "patch", params)

    def domainAuthID(self, domain: str, sendTo: int) -> dict:
        """Returns the authorization code to transfer the domain name to another registrar or to another client account

        Args:
            domain (str): name of the domain to get the AuthID
            sendTo	(int): send the authorization code to 0: Reseller, 1: Registrant, 2: None

        Throws:
            NetimAPIException

        Returns:
            StructOperationResponse: giving information on the status of the operation

        See:
            domainSetDNSsec API http://support.netim.com/en/wiki/DomainSetDNSsec
        """
        domain = domain.lower()

        params = {"sendto": sendTo}
        return self.call("domain/" + domain + "/authid/", "patch", params)

    def domainDSRecordCreate(self, domain: str, data: list) -> dict:
        """Add DS records to a domain if it does not use NETIM’s DNS servers

        Args:
            domain (str):   Domain name
            data (list):    An array of dsData or keyData

        Throws:
            NetimAPIException

        Returns:
            StructOperationResponse: giving information on the status of the operation

        See:
            https://support.netim.com/en/docs/api-rest-3-0/domain-names/ds-record-create
        """
        domain = domain.lower()
        params = {
            "data": data,
        }

        return self.call("/domain/" + domain + "/ds-record/", "post", params)

    def domainDSRecordDelete(self, domain: str, data: list) -> dict:
        """Remove DS records from a domain if it does not use NETIM’s DNS servers

        Args:
            domain (str):   Domain name
            data (list):    An array of dsData or keyData

        Throws:
            NetimAPIException

        Returns:
            StructOperationResponse: giving information on the status of the operation

        See:
            https://support.netim.com/en/docs/api-rest-3-0/domain-names/ds-record-delete
        """
        domain = domain.lower()
        params = {
            "data": data,
        }

        return self.call("/domain/" + domain + "/ds-record/", "delete", params)

    def domainDSRecordDeleteAll(self, domain: str) -> dict:
        """Remove DS records from a domain if it does not use NETIM’s DNS servers

        Args:
            domain (str):   Domain name

        Throws:
            NetimAPIException

        Returns:
            StructOperationResponse: giving information on the status of the operation

        See:
            https://support.netim.com/en/docs/api-rest-3-0/domain-names/ds-record-delete-all
        """
        domain = domain.lower()

        return self.call("/domain/" + domain + "/ds-record/", "delete")

    def domainDSRecordList(self, domain: str) -> dict:
        """Remove DS records from a domain if it does not use NETIM’s DNS servers

        Args:
            domain (str):   Domain name

        Throws:
            NetimAPIException

        Returns:
            Array of dsData or keyData

        See:
            https://support.netim.com/en/docs/api-rest-3-0/domain-names/ds-record-list
        """
        domain = domain.lower()

        return self.call("/domain/" + domain + "/ds-record/", "get")


    def domainPriceList(self, tld: str = "") -> dict:
        """Returns the list of all prices for each tld

        Args:
            tld (str): Filter list on specific domain tld

        Throws:
            NetimAPIException

        Returns:
            StructDomainPriceList[]: An array of StructDomainPriceList

        See:
            domainPriceList API http://support.netim.com/en/wiki/DomainPriceList
        """

        if tld:
            params = {"tld": tld}
            return self.call("/tlds/price-list/", "get", params)
        else:
            return self.call("/tlds/price-list/", "get")

    def domainGetPrices(self, domain: str, authID: str = "") -> dict:
        """Allows to know a domain's price

        Args:
            domain (str): name of domain
            authID (str, optional): authorisation code. Defaults to "".

        Throws:
            NetimAPIException

        Returns:
            StructDomainGetPrices: An object StructDomainGetPrices containing information about a domain's price

        See:
            domainGetPrices API http://support.netim.com/en/wiki/domainGetPrices
        """
        domain = domain.lower()
        if authID:
            params = {"authId": authID}
            return self.call("/domain/" + domain + "/price/", "get", params)
        else:
            return self.call("/domain/" + domain + "/price/", "get")

    def domainCheckClaims(self, domain: str) -> int:
        """Allows to know if there is a claim on the domain name

        Args:
            domain (str): name of domain

        Throws:
            NetimAPIException

        Returns:
            int: 0 = no claim ; 1 = at least one claim
        """
        domain = domain.lower()
        return self.call("/domain/" + domain + "/claim/", "get")

    def domainList(self, filters: dict) -> list:
        """Returns a list of domains matching the filters

        Args:
            filters (dict): Domain list filters

        Throws:
            NetimAPIException

        Returns:
            StructDomainList[]: An array of StructDomainList

        See:
            domainList API http://support.netim.com/en/wiki/domainList
        """

        params = {"filters": filters}
        return self.call("/domains/", "post", params)

    def domainProductInfo(self, tld: str) -> dict:
        """Returns informations about a domain product

        Args:
            tld (dict): Domain tld

        Throws:
            NetimAPIException

        Returns:
            dict: Informations about a domain product
        """

        tld = tld.lower()
        return self.call("/domains/product/" + tld + "/", "get")

    def domainZoneInit(self, domain: str, templateDNS: int) -> dict:
        """Resets all DNS settings from a template

        Args:
            domain (str): Domain name
            templateDNS (int): Template number

        Throws:
            NetimAPIException

        Returns:
            StructOperationResponse: giving information on the status of the operation

        See:
            domainZoneInit API http://support.netim.com/en/wiki/DomainZoneInit
        """
        domain = domain.lower()

        params = {"templateDNS": templateDNS}

        return self.call("/domain/" + domain + "/zone/init/", "patch", params)

    def domainZoneCreate(
        self, domain: str, subdomain: str, type: str, value: str, options: dict
    ) -> dict:
        """Creates a DNS record into the domain zonefile

        Args:
            domain (str): name of the domain
            subdomain (str): subdomain
            type (str): type of DNS record. Accepted values are: 'A', 'AAAA', 'MX, 'CNAME', 'TXT', 'NS and 'SRV'
            value (str): value of the new DNS record
            options (dict): contains multiple StructZoneParam : settings of the new DNS record

        Throws:
            NetimAPIException

        Returns:
            StructOperationResponse: giving information on the status of the operation

        See:
            domainZoneCreate API http://support.netim.com/en/wiki/DomainZoneCreate
            StructZoneParam http://support.netim.com/en/wiki/StructZoneParam
        """
        domain = domain.lower()
        params = {
            "subdomain": subdomain,
            "type": type,
            "value": value,
            "options": options,
        }

        return self.call("/domain/" + domain + "/zone/", "post", params)

    def domainZoneUpdate(
        self, domain: str, subdomain: str, type: str, value: str, newValue: str, options: dict,
    ) -> dict:
        """Creates a DNS record into the domain zonefile

        Args:
                domain (str): name of the domain
                subdomain (str): subdomain
                type (str): type of DNS record. Accepted values are: 'A', 'AAAA', 'MX, 'CNAME', 'TXT', 'NS and 'SRV'
                value (str): current value of the DNS record
                newValue (str): new value of the DNS record
                options (dict): contains multiple StructZoneParam : settings of the new DNS record

        Throws:
                NetimAPIException

        Returns:
                StructOperationResponse: giving information on the status of the operation
        """
        domain = domain.lower()
        params = {
            "subdomain": subdomain,
            "type": type,
            "value": value,
            "newValue": newValue,
            "options": options,
        }

        return self.call("/domain/" + domain + "/zone/update/", "patch", params)

    def domainZoneDelete(
        self, domain: str, subdomain: str, type: str, value: str
    ) -> dict:
        """Deletes a DNS record into the domain's zonefile

        Args:
            domain (str): name of the domain
            subdomain (str): subdomain
            type (str): type of DNS record. Accepted values are: 'A', 'AAAA', 'MX', 'CNAME', 'TXT', 'NS' and 'SRV'
            value (str): value of the new DNS record

        Throws:
            NetimAPIException

        Returns:
            StructOperationResponse: giving information on the status of the operation

        See:
            domainZoneDelete API http://support.netim.com/en/wiki/DomainZoneDelete
        """
        domain = domain.lower()
        params = {
            "subdomain": subdomain,
            "type": type,
            "value": value,
        }

        return self.call("/domain/" + domain + "/zone/", "delete", params)

    def domainZoneInitSoa(
        self,
        domain: str,
        ttl: int,
        ttlUnit: chr,
        refresh: int,
        refreshUnit: chr,
        retry: int,
        retryUnit: chr,
        expire: int,
        expireUnit: chr,
        minimum: int,
        minimumUnit: chr,
    ) -> dict:
        """Resets the SOA record of a domain name

        Args:
           domain (str): name of the domain
           ttl (int): time to live
           ttlUnit (chr): TTL unit. Accepted values are: 'S', 'M', 'H', 'D', 'W'
           refresh (int): Refresh delay
           refreshUnit (chr): Refresh unit. Accepted values are: 'S', 'M', 'H', 'D', 'W'
           retry (int): Retry delay
           retryUnit (chr): Retry unit. Accepted values are: 'S', 'M', 'H', 'D', 'W'
           expire (int): Expire delay
           expireUnit (chr): Expire unit. Accepted values are: 'S', 'M', 'H', 'D', 'W'
           minimum (int): Minimum delay
           minimumUnit (chr): Minimum unit. Accepted values are: 'S', 'M', 'H', 'D', 'W'

        Throws:
            NetimAPIException

        Returns:
            StructOperationResponse: giving information on the status of the operation

        See:
            domainZoneDelete API http://support.netim.com/en/wiki/DomainZoneDelete
        """
        domain = domain.lower()
        params = {
            "ttl": ttl,
            "ttlUnit": ttlUnit,
            "refresh": refresh,
            "refreshUnit": refreshUnit,
            "retry": retry,
            "retryUnit": retryUnit,
            "expire": expire,
            "expireUnit": expireUnit,
            "minimumUnit": minimumUnit,
            "minimum": minimum,
        }

        return self.call("/domain/" + domain + "/zone/init-soa/", "patch", params)

    def domainZoneInfo(
        self,
        domain: str,
    ) -> dict:
        """Returns informations about a DNS zone

        Throws:
            NetimAPIException

        Returns:
            StructOperationResponse: giving information on the status of the operation
        """
        domain = domain.lower()

        return self.call("/domain/" + domain + "/zone/info/", "get")

    def domainZoneCheck(
        self, domain: str, nameservers: dict
    ) -> dict:
        """Investigates the state of the domain name from the top to the bottom of the DNS tree.

        Throws:
            NetimAPIException

        Returns:
            array
        """
        domain = domain.lower()

        params = {"nameservers": nameservers}

        return self.call("domain/" + domain + "/zone/check/", "post", params)

    def domainMailFwdCreate(self, mailBox: str, recipients: str) -> dict:
        """Creates an email address forwarded to recipients

        Args:
            mailBox (str): email adress (or * for a catch-all)
            recipients (str): list of email adresses (separated by commas)

        Throws:
            NetimAPIException

        Returns:
            StructOperationResponse: giving information on the status of the operation

        See:
            domainMailFwdCreate API http://support.netim.com/en/wiki/DomainMailFwdCreate
        """
        mailBox = mailBox.lower()
        params = {
            "recipients": recipients,
        }
        return self.call("/domain/" + mailBox + "/mail-forwarding/", "post", params)

    def domainMailFwdDelete(self, mailBox: str) -> dict:
        """Deletes an email forward

        Args:
            mailBox (str): email adress

        Throws:
            NetimAPIException

        Returns:
            StructOperationResponse: giving information on the status of the operation

        See:
            domainMailFwdDelete API http://support.netim.com/en/wiki/DomainMailFwdDelete
        """
        mailBox = mailBox.lower()
        return self.call("/domain/" + mailBox + "/mail-forwarding/", "delete")

    def domainMailFwdList(self, domain: str) -> list:
        """Returns all email forwards for a domain name

        Args:
            domain (str): Domain name

        Throws:
            NetimAPIException

        Returns:
            StructDomainMailFwdList[]: A list of StructDomainMailFwdList
        """
        domain = domain.lower()
        return self.call("/domain/" + domain + "/mail-forwardings/", "get")

    def domainWebFwdCreate(
        self, fqdn: str, target: str, type: str, options: dict
    ) -> dict:
        """Creates a web forwarding

        Args:
            fqdn (str): hostname (fully qualified domain name)
            target (str): target of the web forwarding
            type (str): type of the web forwarding. Accepted values are: "DIRECT", "IP", "MASKED" or "PARKING"
            options (dict): contains StructOptionsFwd : settings of the web forwarding. An array with keys: header, protocol, title and parking.

        Throws:
            NetimAPIException

        Returns:
            StructOperationResponse: giving information on the status of the operation

        See:
            domainWebFwdCreate API http://support.netim.com/en/wiki/DomainWebFwdCreate
            StructOptionsFwd http://support.netim.com/en/wiki/StructOptionsFwd
        """
        params = {
            "target": target,
            "type": type.upper(),
            "options": options,
        }

        return self.call("/domain/" + fqdn + "/web-forwarding/", "post", params)

	def domainWebFwdUpdate(
		self, fqdn: str, target: str, type: str, options: dict
	) -> dict:
		"""Updates a web forwarding

		Args:
			fqdn (str): hostname (fully qualified domain name)
			target (str): target of the web forwarding
			type (str): type of the web forwarding. Accepted values are: "DIRECT", "IP", "MASKED" or "PARKING"
			options (dict): contains StructOptionsFwd : settings of the web forwarding. An array with keys: header, protocol, title, parking and https.

		Throws:
			NetimAPIException

		Returns:
			StructOperationResponse: giving information on the status of the operation
		"""

		params = {
			"target": target,
			"type": type.upper(),
			"options": options,
		}

		return self.call("/domain/" + fqdn + "/web-forwarding/", "patch", params)

    def domainWebFwdDelete(self, fqdn: str) -> dict:
        """Removes a web forwarding

        Args:
            fqdn (str): hostname, a fully qualified domain name

        Throws:
            NetimAPIException

        Returns:
            StructOperationResponse: giving information on the status of the operation

        See:
            domainWebFwdDelete API http://support.netim.com/en/wiki/DomainWebFwdDelete
        """
        return self.call("/domain/" + fqdn + "/web-forwarding/", "delete")

    def domainWebFwdList(self, domain: str) -> list:
        """Return all web forwarding of a domain name

        Args:
            domain (str): Domain name

        Throws:
            NetimAPIException

        Returns:
            StructDomainWebFwdList[]: A list of StructDomainWebFwdList
        """
        domain = domain.lower()
        return self.call("/domain/" + domain + "/web-forwardings/", "get")

    def sslCreate(
        self, prod: str, duration: int, CSRInfo: dict, validation: str
    ) -> dict:
        """Creates a SSL redirection

        Args:
            prod (str): certificate type
            duration (int): period of validity (in years)
            CSRInfo (dict): containing informations about the CSR
            validation (str): validation method of the CSR (either by email or file) :
                "file"
                        "email:admin@yourdomain.com"
                        "email:postmaster@yourdomain.com,webmaster@yourdomain.com"

        Throws:
            NetimAPIException

        Returns:
            StructOperationResponse: giving information on the status of the operation

        See:
            sslCreate API http://support.netim.com/en/wiki/SslCreate
            StructCSR https://support.netim.com/fr/wiki/StructCSR
        """
        params = {
            "prod": prod,
            "duration": duration,
            "CSR": CSRInfo,
            "validation": validation,
        }

        return self.call("/ssl/", "post", params)

    def sslRenew(self, IDSSL: str, duration: int) -> dict:
        """Renew a SSL certificate for a new subscription period.

        Args:
            IDSSL (str): SSL certificate ID
            duration (int): period of validity after the renewal (in years). Only the value 1 is valid

        Throws:
            NetimAPIException

        Returns:
            StructOperationResponse: giving information on the status of the operation

        See:
            sslRenew API http://support.netim.com/en/wiki/SslRenew
        """
        params = {"duration": duration}

        return self.call("/ssl/" + IDSSL + "/renew/", "patch", params)

    def sslRevoke(self, IDSSL: str) -> dict:
        """Revokes a SSL Certificate.

        Args:
            IDSSL (str): SSL certificate ID

        Throws:
            NetimAPIException

        Returns:
            StructOperationResponse: giving information on the status of the operation

        See:
            sslRenew API http://support.netim.com/en/wiki/SslRenew
        """
        return self.call("/ssl/" + IDSSL + "/", "delete")

    def sslReIssue(self, IDSSL: str, CSRInfo: dict, validation: str) -> dict:
        """Reissues a SSL Certificate.

        Args:
            IDSSL (str): SSL certificate ID
            CSRInfo (dict): Object containing informations about the CSR
            validation (str): validation method of the CSR (either by email or file) :
                "file"
                "email:admin@yourdomain.com"
                "email:postmaster@yourdomain.com,webmaster@yourdomain.com"

        Throws:
            NetimAPIException

        Returns:
            StructOperationResponse: giving information on the status of the operation

        See:
            sslCreate API http://support.netim.com/en/wiki/SslCreate
            StructCSR https://support.netim.com/fr/wiki/StructCSR
        """
        params = {
            "CSR": CSRInfo,
            "validation": validation,
        }

        return self.call("/ssl/" + IDSSL + "/reissue/", "patch", params)

    def sslSetPreference(self, IDSSL: str, codePref: str, value: str) -> dict:
        """Updates the settings of a SSL certificate. Currently, only the autorenew setting can be modified.

        Args:
            IDSSL (str): SSL certificate ID
            codePref (str): Setting to be modified (auto_renew/to_be_renewed)
            value (str): New value of the setting

        Throws:
            NetimAPIException

        Returns:
            StructOperationResponse: giving information on the status of the operation

        See:
            sslSetPreference API http://support.netim.com/en/wiki/SslSetPreference
        """
        params = {
            "codePref": codePref,
            "value": value,
        }

        return self.call("/ssl/" + IDSSL + "/preference/", "patch", params)

    def sslInfo(self, IDSSL: str) -> dict:
        """Returns all the informations about a SSL certificate

        Args:
            IDSSL (str): SSL certificate ID

        Throws:
            NetimAPIException

        Returns:
            StructSSLInfo: containing the SSL certificate informations

        See:
            sslInfo API http://support.netim.com/en/wiki/SslInfo
        """
        return self.call("/ssl/" + IDSSL + "/", "get")


    def sslList(self, filters: dict) -> list:
        """List SSL certificates matching filters

        Throws:
            NetimAPIException

        Returns:
            array
        """
        params = {"filters": filters}
        return self.call("ssl/list/", "post", params)
    
    def sslPriceList(self, product: str = "") -> dict:
        """Returns the list of all prices for SSL products

        Args:
            product (str): SSL product ID

        Throws:
            NetimAPIException

        Returns:
            dict: array
        """

        if product:
            return self.call("/ssl/price/" + product, "get")
        else:
            return self.call("ssl/price/", "get")

    def sslProductInfo(self, product: str) -> dict:
        """Returns informations about a SSL product

        Args:
            tld (dict): SSL product

        Throws:
            NetimAPIException

        Returns:
            dict: Informations about a SSL product
        """

        product = product.upper()
        return self.call("/ssl/product/" + product + "/", "get")


    def brandProtectionCreate(
        self, label: str, product: str, duration: int, idOwner: str, type: str, infos: dict
    ) -> dict:
        """Create a new brand protection

        Args:
            label (str): Brand main label
            product (str): Brand protection product ID
            duration (int): Period of validity in years
            idOwner (str): ID of the owner contact
            type (str): Brand’s type
            infos (dict): Array of strings containing brand datas

        Throws:
            NetimAPIException

        Returns:
            dict: StructOperationResponse
        """
        params = {
            "label": label,
            "prod": product,
            "duration": duration,
            "idOwner": idOwner,
            "type": type,
            "info": infos,
        }

        return self.call("brandprotection/", "post", params)

    def brandProtectionInfo(
        self, id: str
    ) -> dict:
        """Return all information about a brand protection

        Args:
            id (str): Brand protection ID

        Throws:
            NetimAPIException

        Returns:
            dict: StructBrandProtectionInfo
        """
        return self.call("brandprotection/" + id + "/", "get")

    def brandProtectionProductInfo(
        self, product: str
    ) -> dict:
        """Return all information about a brand protection product

        Args:
            product (str): Brand protection product ID

        Throws:
            NetimAPIException

        Returns:
            dict: array
        """
        return self.call("brandprotection/product/" + product + "/", "get")
    
    def brandProtectionPriceList(self, product: str = "") -> dict:
        """Returns the list of all prices for brand protection products

        Args:
            product (str):Brand protection product ID

        Throws:
            NetimAPIException

        Returns:
            dict: array
        """

        if product:
            return self.call("/brandprotection/price/" + product, "get")
        else:
            return self.call("brandprotection/price/", "get")

    def brandProtectionList(
        self, filters: dict
    ) -> list:
        """List brand protections matching filters

        Args:
            filters (dict): Search filters

        Throws:
            NetimAPIException

        Returns:
            list: array
        """
        params = {"filters": filters}
        return self.call("brandprotection/list/", "post", params)

    def brandProtectionTransferOwner(
        self, id: str, idOwner: str
    ) -> dict:
        """Request the transfer of the ownership to another party

        Args:
            id (str): Brand protection ID
            idOwner (str): ID of the owner contact

        Throws:
            NetimAPIException

        Returns:
            dict: StructOperationResponse
        """
        params = {"idOwner": idOwner}
        return self.call("brandprotection/" + id + "/transfer-owner/", "put", params)

    def brandProtectionRenew(
        self, id: str, duration: int
    ) -> dict:
        """Renew a brand protection for a new period

        Args:
            id (str): Brand protection ID
            duration (int): Duration in years

        Throws:
            NetimAPIException

        Returns:
            dict: StructOperationResponse
        """
        params = {"duration": duration}
        return self.call("brandprotection/" + id + "/renew/", "patch", params)

    def brandProtectionDelete(
        self, id: str
    ) -> dict:
        """Delete a brand protection

        Args:
            id (str): Brand protection ID

        Throws:
            NetimAPIException

        Returns:
            dict: StructOperationResponse
        """
        return self.call("brandprotection/" + id + "/", "delete")

    def brandProtectionSetPreference(
        self, id: str, codePref: str, enable: str
    ) -> dict:
        """Set brand protection preference

        Args:
            id (str): Brand protection ID
            codePref (str): Preference to update ("auto_renew", "to_be_renewed")
            enable (str): "0" to disable, "1" to enable

        Throws:
            NetimAPIException

        Returns:
            dict: StructOperationResponse
        """
        params = {
            "codePref": codePref,
            "enable": enable,
        }
        return self.call("brandprotection/" + id + "/preference/", "patch", params)
