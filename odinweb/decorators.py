"""
Decorators
~~~~~~~~~~

A collection of decorators for identifying the various types of route.

"""
from __future__ import absolute_import

from typing import Callable, Union, Tuple, Dict, Any, Optional, Generator, List  # noqa

from odin import Resource
from odin.utils import force_tuple, lazy_property

from .constants import HTTPStatus, Method, Type
from .data_structures import NoPath, UrlPath, HttpResponse, PathNode, Param, Response, DefaultResponse
from .helpers import get_resource
from .resources import Listing, Error
from .utils import to_bool, dict_filter, make_decorator

__all__ = (
    'Operation', 'ListOperation', 'ResourceOperation',
    # Basic routes
    'collection', 'collection_action', 'action', 'operation',
    # Shortcuts
    'listing', 'create', 'detail', 'update', 'patch', 'delete',
)

# Type definitions
Tags = Union[str, Tuple[str]]
HttpRequest = Any
PreDispatch = Callable[[HttpRequest, Dict[str, Any]], HttpResponse]
PostDispatch = Callable[[HttpRequest, HttpResponse], HttpResponse]


class Operation(object):
    """
    Decorator for defining an API operation. Usually one of the helpers (listing, detail, update, delete) would be
    used in place of this route decorator.

    Usage::

        class ItemApi(ResourceApi):
            resource = Item

            @route(path=PathType.Collection, methods=Method.GET)
            def list_items(self, request):
                ...
                return items

    """
    _operation_count = 0

    def __new__(cls, func=None, *args, **kwargs):
        def inner(callback):
            instance = super(Operation, cls).__new__(cls)
            instance.__init__(callback, *args, **kwargs)
            return instance
        return inner(func) if func else inner

    def __init__(self, callback, url_path=NoPath, methods=Method.GET, resource=None, tags=None, summary=None):
        # type: (Callable, UrlPath, Union(Method, Tuple[Method]), Optional[Resource], Tags, Optional(str)) -> None
        """
        :param callback: Function we are routing
        :param url_path: A sub path that can be used as a action.
        :param methods: HTTP method(s) this function responses to.
        :param resource: Specify the resource that this function encodes/decodes,
            default is the one specified on the ResourceAPI instance.
        :param tags: Tags to be applied to operation
        """
        self.base_callback = self.callback = callback
        self.url_path = UrlPath.from_object(url_path)
        self.methods = force_tuple(methods)
        self._resource = resource

        # Sorting/hashing
        self.sort_key = Operation._operation_count
        Operation._operation_count += 1

        # If this operation is bound to a ResourceAPI
        self.binding = None

        # Dispatch hooks
        self._pre_dispatch = getattr(self, 'pre_dispatch', None)  # type: PreDispatch
        self._post_dispatch = getattr(self, 'post_dispatch', None)  # type: PostDispatch

        # Documentation
        self.deprecated = False
        self.summary = summary
        self.consumes = set()
        self.produces = set()
        self.responses = set()
        self.parameters = set()
        self._tags = set(force_tuple(tags))

        # Copy values from callback (if defined)
        for attr in ('deprecated', 'consumes', 'produces', 'responses', 'parameters'):
            value = getattr(callback, attr, None)
            if value is not None:
                setattr(self, attr, value)

        # Add a default response
        self.responses.add(DefaultResponse('Unhandled error', Error))

    def __call__(self, request, path_args):
        # type: (HttpRequest, Dict[Any]) -> Any
        """
        Main wrapper around the operation callback function.
        """
        # Allow for a pre_dispatch hook, path_args is passed by ref so changes can be made.
        if self._pre_dispatch:
            self._pre_dispatch(request, path_args)

        response = self.execute(request, **path_args)

        # Allow for a post_dispatch hook, the response of which is returned
        if self._post_dispatch:
            return self._post_dispatch(request, response)
        else:
            return response

    def execute(self, request, *args, **path_args):
        # type: (HttpRequest, tuple, Dict[Any]) -> Any
        """
        Execute the callback (binding callback if required)
        """
        binding = self.binding
        if binding:
            # Provide binding as decorators are executed prior to binding
            return self.callback(binding, request, *args, **path_args)
        else:
            return self.callback(request, *args, **path_args)

    def bind_to_instance(self, instance):
        """
        Bind a ResourceApi instance to an operation.
        """
        self.binding = instance

        # Configure hooks
        if self._pre_dispatch is None:
            self._pre_dispatch = getattr(instance, 'pre_dispatch', None)
        if self._post_dispatch is None:
            self._post_dispatch = getattr(instance, 'pos_dispatch', None)

    def op_paths(self, path_prefix=None):
        # type: (Optional[Union[str, UrlPath]]) -> Generator[Tuple[UrlPath, Operation]]
        """
        Yield operations paths stored in containers.
        """
        url_path = self.url_path
        if path_prefix:
            url_path = path_prefix + url_path

        yield url_path, self

    @lazy_property
    def resource(self):
        """
        Resource associated with operation.
        """
        if self._resource:
            return self._resource
        elif self.binding:
            return self.binding.resource

    @property
    def is_bound(self):
        # type: () -> bool
        """
        Operation is bound to a resource api
        """
        return bool(self.binding)

    # Docs ####################################################################

    def to_doc(self):
        """
        Generate a dictionary for documentation generation.
        """
        return dict_filter(
            operationId=self.operation_id,
            description=(self.callback.__doc__ or '').strip(),
            summary=self.summary,
            tags=self.tags if self.tags else None,
            deprecated=True if self.deprecated else None,
            consumes=self.consumes if self.consumes else None,
            parameters=[param.to_swagger(self.resource) for param in self.parameters],
            produces=list(self.produces) if self.produces else None,
            responses=dict(resp.to_swagger(self.resource) for resp in self.responses) if self.responses else None,
        )

    @lazy_property
    def operation_id(self):
        return self.base_callback.__name__

    @property
    def tags(self):
        # type: () -> List[str]
        """
        Tags applied to operation.
        """
        tags = []
        if self._tags:
            tags.extend(self._tags)
        if self.binding:
            binding_tags = getattr(self.binding, 'tags', None)
            if binding_tags:
                tags.extend(binding_tags)
        return tags

collection = collection_action = action = operation = Operation


class ListOperation(Operation):
    """
    Decorator to indicate a listing endpoint.

    Usage::

        class ItemApi(ResourceApi):
            resource = Item

            @listing(path=PathType.Collection, methods=Method.Get)
            def list_items(self, request, offset, limit):
                ...
                return items

    """
    listing_resource = Listing
    default_offset = 0
    default_limit = 50
    max_offset = None
    max_limit = None

    def __init__(self, *args, **kwargs):
        self.listing_resource = kwargs.pop('listing_resource', self.listing_resource)
        self.default_offset = kwargs.pop('default_offset', self.default_offset)
        self.default_limit = kwargs.pop('default_limit', self.default_limit)
        self.max_offset = kwargs.pop('max_offset', self.max_offset)
        self.max_limit = kwargs.pop('max_limit', self.max_limit)

        super(ListOperation, self).__init__(*args, **kwargs)

        # Apply documentation
        self.parameters.add(Param.query('offset', Type.Integer, "Offset to start listing from.",
                                        default=self.default_offset, maximum=self.max_offset))
        self.parameters.add(Param.query('limit', Type.Integer, "Limit on the number of listings returned.",
                                        default=self.default_limit, maximum=self.max_limit))
        self.parameters.add(Param.query('bare', Type.Boolean, "Return a plain list of objects."))

    def execute(self, request, *args, **path_args):
        # Get paging args from query string
        max_offset = self.max_offset
        offset = int(request.GET.get('offset', self.default_offset))
        if offset < 0:
            offset = 0
        elif max_offset and offset > max_offset:
            offset = max_offset
        path_args['offset'] = offset

        max_limit = self.max_limit
        limit = int(request.GET.get('limit', self.default_limit))
        if limit < 1:
            limit = 1
        elif max_limit and limit > max_limit:
            limit = max_limit
        path_args['limit'] = limit

        bare = to_bool(request.GET.get('bare', False))

        # Run base execute
        result = super(ListOperation, self).execute(request, *args, **path_args)
        if result is not None:
            if isinstance(result, tuple) and len(result) == 2:
                result, total_count = result
            else:
                total_count = None

            return result if bare else Listing(result, limit, offset, total_count)


class ResourceOperation(Operation):
    """
    Handle processing a request with a resource body.

    It is assumed decorator will operate on a class method.
    """
    def __init__(self, *args, **kwargs):
        super(ResourceOperation, self).__init__(*args, **kwargs)

        # Apply documentation
        self.parameters.add(Param.body('Expected resource supplied with request.'))

    def execute(self, request, *args, **path_args):
        item = get_resource(request, self.resource) if self.resource else None
        return super(ResourceOperation, self).execute(request, item, *args, **path_args)


# Shortcut methods

@make_decorator
def listing(callback, resource=None, default_limit=50, max_limit=None, tags=None, summary="List resources"):
    """
    Decorator to configure an operation that returns a list of resources.

    :param callback: Operation callback
    :param resource: Specify the resources that operation returns. Default is the resource specified on the bound
        `ResourceAPI` instance.
    :param default_limit: Default limit on responses; defaults to 50.
    :param max_limit: Maximum limit value.
    :param tags: Any tags to apply to operation.
    :param summary: Summary of the operation.

    """
    op = ListOperation(callback, NoPath, Method.GET, resource, tags, summary,
                       default_limit=default_limit, max_limit=max_limit)
    op.responses.add(Response(HTTPStatus.OK, "Listing of resources", Listing))
    return op


@make_decorator
def create(callback, resource=None, tags=None, summary="Create a new resource"):
    """
    Decorator to configure an operation that creates a resource.

    :param callback: Operation callback
    :param resource: Specify the resource that operation accepts and returns. Default is the resource specified on the
        bound `ResourceAPI` instance.
    :param tags: Any tags to apply to operation.
    :param summary: Summary of the operation.

    """
    op = ResourceOperation(callback, NoPath, Method.POST, resource, tags, summary)
    op.responses.add(Response(HTTPStatus.CREATED, "{name} has been created"))
    op.responses.add(Response(HTTPStatus.BAD_REQUEST, "Validation failed.", Error))
    return op


@make_decorator
def detail(callback, resource=None, tags=None, summary="Get specified resource."):
    """
    Decorator to configure an operation that fetches a resource.

    :param callback: Operation callback
    :param resource: Specify the resource that operation returns. Default is the resource specified on the bound
        `ResourceAPI` instance.
    :param tags: Any tags to apply to operation.
    :param summary: Summary of the operation.

    """
    op = Operation(callback, PathNode('resource_id'), Method.GET, resource, tags, summary)
    op.responses.add(Response(HTTPStatus.OK, "Get a {name}"))
    op.responses.add(Response(HTTPStatus.NOT_FOUND, "Not found", Error))
    return op


@make_decorator
def update(callback, resource=None, tags=None, summary="Update specified resource."):
    """
    Decorator to configure an operation that updates a resource.

    :param callback: Operation callback
    :param resource: Specify the resource that operation accepts and returns. Default is the resource specified on the
        bound `ResourceAPI` instance.
    :param tags: Any tags to apply to operation.
    :param summary: Summary of the operation.

    """
    op = ResourceOperation(callback, PathNode('resource_id'), Method.PUT, resource, tags, summary)
    op.responses.add(Response(HTTPStatus.NO_CONTENT, "{name} has been updated."))
    op.responses.add(Response(HTTPStatus.BAD_REQUEST, "Validation failed.", Error))
    op.responses.add(Response(HTTPStatus.NOT_FOUND, "Not found", Error))
    return op


@make_decorator
def patch(callback, resource=None, tags=None, summary="Patch specified resource."):
    """
    Decorator to configure an operation that patches a resource.

    :param callback: Operation callback
    :param resource: Specify the resource that operation partially accepts and returns. Default is the resource
        specified on the bound `ResourceAPI` instance.
    :param tags: Any tags to apply to operation.
    :param summary: Summary of the operation.

    """
    op = ResourceOperation(callback, PathNode('resource_id'), Method.PATCH, resource, tags, summary)
    op.responses.add(Response(HTTPStatus.OK, "{name} has been patched."))
    op.responses.add(Response(HTTPStatus.BAD_REQUEST, "Validation failed.", Error))
    op.responses.add(Response(HTTPStatus.NOT_FOUND, "Not found", Error))
    return op


@make_decorator
def delete(callback, tags=None, summary="Delete specified resource."):
    """
    Decorator to configure an operation that deletes resource.

    :param callback: Operation callback
    :param tags: Any tags to apply to operation.
    :param summary: Summary of the operation.

    """
    op = Operation(callback, PathNode('resource_id'), Method.DELETE, None, tags, summary)
    op.responses.add(Response(HTTPStatus.NO_CONTENT, "{name} has been deleted.", None))
    op.responses.add(Response(HTTPStatus.NOT_FOUND, "Not found", Error))
    return op
