"""Exceptions specific to the Prereq Module."""


class PrereqError(Exception): ...


class ProviderNotFoundError(PrereqError, RuntimeError): ...
