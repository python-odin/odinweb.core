"""
Decorators
~~~~~~~~~~

A collection of decorators for identifying the various types of route.

"""
from __future__ import absolute_import, unicode_literals


import six

from collections import namedtuple
from functools import wraps

from . import constants
from .resources import Listing

__all__ = (
    # Basic routes
    'route', 'collection', 'collection_action', 'resource_action',
    # Pending deprecation routes
    'detail_route', 'action', 'detail_action',
    # Handlers
    'list_response',
    # Shortcuts
    'listing', 'create', 'detail', 'update', 'patch', 'delete'
)

# Counter used to order routes
_route_count = 0


RouteDefinition = namedtuple("RouteDefinition", ('route_number', 'path_type', 'methods', 'name'))


def route(func=None, name=None, path_type=constants.PATH_TYPE_COLLECTION, methods=constants.GET, resource=None):
    """
    Decorator for defining an API route. Usually one of the helpers (listing, detail, update, delete) would be
    used in place of the route decorator.

    Usage::

        class ItemApi(ResourceApi):
            resource = Item

            @route(path=PATH_TYPE_LIST, methods=GET)
            def list_items(self, request):
                ...
                return items

    :param func: Function we are routing
    :param name: Action name
    :param path_type: Type of path, list/detail or custom.
    :param methods: HTTP method(s) this function responses to.
    :type methods: str | tuple(str) | list(str)
    :param resource: Specify the resource that this function encodes/decodes,
        default is the one specified on the ResourceAPI instance.

    """
    if isinstance(methods, six.string_types):
        methods = (methods, )

    # Generate a route number
    global _route_count
    route_number = _route_count
    _route_count += 1

    def inner(f):
        f.route = RouteDefinition(route_number, path_type, methods, name)
        f.resource = resource
        return f

    return inner(func) if func else inner

collection = collection_action = action = route


def resource_route(func=None, name=None, method=constants.GET, resource=None):
    return route(func, name, constants.PATH_TYPE_RESOURCE, method, resource)

resource_action = resource_route


# Handlers

def list_response(func=None, default_offset=0, default_limit=50):
    """
    Handle processing a list. It is assumed decorator will operate on a class.

    This decorator extracts offer/limit values from the query string and returns
    a Listing response and applies total counts.

    """
    def inner(f):
        @wraps(f)
        def wrapper(self, request, *args, **kwargs):
            # Get paging args from query string
            offset = kwargs['offset'] = int(request.GET.get('offset', default_offset))
            limit = kwargs['limit'] = int(request.GET.get('limit', default_limit))
            result = f(self, request, *args, **kwargs)
            if result is not None:
                if isinstance(result, tuple) and len(result) == 2:
                    result, total_count = result
                else:
                    total_count = None
                return Listing(list(result), limit, offset, total_count)
        return wrapper
    return inner(func) if func else inner


# Shortcut method

def listing(func=None, name=None, resource=None, default_offset=0, default_limit=50):
    """
    Decorator to indicate a listing endpoint.

    :param func: Function we are routing
    :param name: Action name
    :param resource: Specify the resource that this function
        encodes/decodes, default is the one specified on the ResourceAPI
        instance.
    :param default_offset: Default value for the offset from the start of listing.
    :param default_limit: Default value for limiting the response size.

    """
    return route(list_response(func, default_offset, default_limit),
                 name, constants.PATH_TYPE_COLLECTION, constants.GET, resource)


def create(func=None, name=None, resource=None):
    """
    Decorator to indicate a creation endpoint.

    :param func: Function we are routing
    :param name: Action name
    :param resource: Specify the resource that this function
        encodes/decodes, default is the one specified on the ResourceAPI
        instance.

    """
    return route(func, name, constants.PATH_TYPE_COLLECTION, constants.POST, resource)


def detail(func=None, name=None, resource=None):
    """
    Decorator to indicate a detail endpoint.

    :param func: Function we are routing
    :param name: Action name
    :param resource: Specify the resource that this function
        encodes/decodes, default is the one specified on the ResourceAPI
        instance.

    """
    return route(func, name, constants.PATH_TYPE_RESOURCE, constants.GET, resource)


def update(func=None, name=None, resource=None):
    """
    Decorator to indicate an update endpoint.

    :param func: Function we are routing
    :param name: Action name
    :param resource: Specify the resource that this function
        encodes/decodes, default is the one specified on the ResourceAPI
        instance.

    """
    return route(func, name, constants.PATH_TYPE_RESOURCE, constants.PUT, resource)


def patch(func=None, name=None, resource=None):
    """
    Decorator to indicate a patch endpoint.

    :param func: Function we are routing
    :param name: Action name
    :param resource: Specify the resource that this function
        encodes/decodes, default is the one specified on the ResourceAPI
        instance.

    """
    return route(func, name, constants.PATH_TYPE_RESOURCE, constants.PATCH, resource)


def delete(func=None, name=None, resource=None):
    """
    Decorator to indicate a deletion endpoint.

    :param func: Function we are routing
    :param name: Action name
    :param resource: Specify the resource that this function
        encodes/decodes, default is the one specified on the ResourceAPI
        instance.

    """
    return route(func, name, constants.PATH_TYPE_RESOURCE, constants.DELETE, resource)
