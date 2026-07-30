/upload-erp?profile_id=24 HTTP/1.1" 200 OK
INFO:     127.0.0.1:50936 - "OPTIONS /api/v1/purchases/upload?session_id=8729747a-8c1e-4f84-94df-5914098a01cf HTTP/1.1" 200 OK
INFO:     127.0.0.1:50936 - "POST /api/v1/purchases/upload?session_id=8729747a-8c1e-4f84-94df-5914098a01cf HTTP/1.1" 200 OK
INFO:     127.0.0.1:50936 - "POST /api/v1/reconciliation/compare HTTP/1.1" 200 OK
INFO:     127.0.0.1:50936 - "OPTIONS /api/v1/sessions/8729747a-8c1e-4f84-94df-5914098a01cf/results?page=1&limit=100 HTTP/1.1" 200 OK
INFO:     127.0.0.1:50936 - "GET /api/v1/sessions/8729747a-8c1e-4f84-94df-5914098a01cf/results?page=1&limit=100 HTTP/1.1" 500 Internal Server Error
ERROR:    Exception in ASGI application
Traceback (most recent call last):
  File "/home/amar-salim/Documents/Projects/kra-reconciliation-api/.venv/lib/python3.14/site-packages/uvicorn/protocols/http/httptools_impl.py", line 422, in run_asgi
    result = await app(  # type: ignore[func-returns-value]
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
        self.scope, self.receive, self.send
        ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
    )
    ^
  File "/home/amar-salim/Documents/Projects/kra-reconciliation-api/.venv/lib/python3.14/site-packages/uvicorn/middleware/proxy_headers.py", line 63, in __call__
    return await self.app(scope, receive, send)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/home/amar-salim/Documents/Projects/kra-reconciliation-api/.venv/lib/python3.14/site-packages/fastapi/applications.py", line 1163, in __call__
    await super().__call__(scope, receive, send)
  File "/home/amar-salim/Documents/Projects/kra-reconciliation-api/.venv/lib/python3.14/site-packages/starlette/applications.py", line 90, in __call__
    await self.middleware_stack(scope, receive, send)
  File "/home/amar-salim/Documents/Projects/kra-reconciliation-api/.venv/lib/python3.14/site-packages/starlette/middleware/errors.py", line 186, in __call__
    raise exc
  File "/home/amar-salim/Documents/Projects/kra-reconciliation-api/.venv/lib/python3.14/site-packages/starlette/middleware/errors.py", line 164, in __call__
    await self.app(scope, receive, _send)
  File "/home/amar-salim/Documents/Projects/kra-reconciliation-api/.venv/lib/python3.14/site-packages/starlette/middleware/cors.py", line 96, in __call__
    await self.simple_response(scope, receive, send, request_headers=headers)
  File "/home/amar-salim/Documents/Projects/kra-reconciliation-api/.venv/lib/python3.14/site-packages/starlette/middleware/cors.py", line 154, in simple_response
    await self.app(scope, receive, send)
  File "/home/amar-salim/Documents/Projects/kra-reconciliation-api/.venv/lib/python3.14/site-packages/starlette/middleware/exceptions.py", line 63, in __call__
    await wrap_app_handling_exceptions(self.app, conn)(scope, receive, send)
  File "/home/amar-salim/Documents/Projects/kra-reconciliation-api/.venv/lib/python3.14/site-packages/starlette/_exception_handler.py", line 53, in wrapped_app
    raise exc
  File "/home/amar-salim/Documents/Projects/kra-reconciliation-api/.venv/lib/python3.14/site-packages/starlette/_exception_handler.py", line 42, in wrapped_app
    await app(scope, receive, sender)
  File "/home/amar-salim/Documents/Projects/kra-reconciliation-api/.venv/lib/python3.14/site-packages/fastapi/middleware/asyncexitstack.py", line 18, in __call__
    await self.app(scope, receive, send)
  File "/home/amar-salim/Documents/Projects/kra-reconciliation-api/.venv/lib/python3.14/site-packages/starlette/routing.py", line 660, in __call__
    await self.middleware_stack(scope, receive, send)
  File "/home/amar-salim/Documents/Projects/kra-reconciliation-api/.venv/lib/python3.14/site-packages/fastapi/routing.py", line 2683, in app
    await route.handle(scope, receive, send)
  File "/home/amar-salim/Documents/Projects/kra-reconciliation-api/.venv/lib/python3.14/site-packages/fastapi/routing.py", line 1753, in handle
    await self.original_router.handle(scope, receive, send)
  File "/home/amar-salim/Documents/Projects/kra-reconciliation-api/.venv/lib/python3.14/site-packages/fastapi/routing.py", line 2738, in handle
    await included_router._handle_selected(scope, receive, send)
  File "/home/amar-salim/Documents/Projects/kra-reconciliation-api/.venv/lib/python3.14/site-packages/fastapi/routing.py", line 1764, in _handle_selected
    await route.handle(scope, receive, send)
  File "/home/amar-salim/Documents/Projects/kra-reconciliation-api/.venv/lib/python3.14/site-packages/fastapi/routing.py", line 1753, in handle
    await self.original_router.handle(scope, receive, send)
  File "/home/amar-salim/Documents/Projects/kra-reconciliation-api/.venv/lib/python3.14/site-packages/fastapi/routing.py", line 2738, in handle
    await included_router._handle_selected(scope, receive, send)
  File "/home/amar-salim/Documents/Projects/kra-reconciliation-api/.venv/lib/python3.14/site-packages/fastapi/routing.py", line 1773, in _handle_selected
    await original_route.handle(scope, receive, send)
  File "/home/amar-salim/Documents/Projects/kra-reconciliation-api/.venv/lib/python3.14/site-packages/fastapi/routing.py", line 1264, in handle
    await app(scope, receive, send)
  File "/home/amar-salim/Documents/Projects/kra-reconciliation-api/.venv/lib/python3.14/site-packages/fastapi/routing.py", line 150, in app
    await wrap_app_handling_exceptions(app, request)(scope, receive, send)
  File "/home/amar-salim/Documents/Projects/kra-reconciliation-api/.venv/lib/python3.14/site-packages/starlette/_exception_handler.py", line 53, in wrapped_app
    raise exc
  File "/home/amar-salim/Documents/Projects/kra-reconciliation-api/.venv/lib/python3.14/site-packages/starlette/_exception_handler.py", line 42, in wrapped_app
    await app(scope, receive, sender)
  File "/home/amar-salim/Documents/Projects/kra-reconciliation-api/.venv/lib/python3.14/site-packages/fastapi/routing.py", line 136, in app
    response = await f(request)
               ^^^^^^^^^^^^^^^^
  File "/home/amar-salim/Documents/Projects/kra-reconciliation-api/.venv/lib/python3.14/site-packages/fastapi/routing.py", line 690, in app
    raw_response = await run_endpoint_function(
                   ^^^^^^^^^^^^^^^^^^^^^^^^^^^^
    ...<3 lines>...
    )
    ^
  File "/home/amar-salim/Documents/Projects/kra-reconciliation-api/.venv/lib/python3.14/site-packages/fastapi/routing.py", line 346, in run_endpoint_function
    return await run_in_threadpool(dependant.call, **values)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/home/amar-salim/Documents/Projects/kra-reconciliation-api/.venv/lib/python3.14/site-packages/starlette/concurrency.py", line 34, in run_in_threadpool
    return await anyio.to_thread.run_sync(func)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/home/amar-salim/Documents/Projects/kra-reconciliation-api/.venv/lib/python3.14/site-packages/anyio/to_thread.py", line 63, in run_sync
    return await get_async_backend().run_sync_in_worker_thread(
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
        func, args, abandon_on_cancel=abandon_on_cancel, limiter=limiter
        ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
    )
    ^
  File "/home/amar-salim/Documents/Projects/kra-reconciliation-api/.venv/lib/python3.14/site-packages/anyio/_backends/_asyncio.py", line 2596, in run_sync_in_worker_thread
    return await future
           ^^^^^^^^^^^^
  File "/home/amar-salim/Documents/Projects/kra-reconciliation-api/.venv/lib/python3.14/site-packages/anyio/_backends/_asyncio.py", line 1029, in run
    result = context.run(func, *args)
  File "/home/amar-salim/Documents/Projects/kra-reconciliation-api/app/api/v1/sessions.py", line 132, in get_session_reconciliation_results
    inv_type = InvoiceType(raw_type) if raw_type in [e.value for e in InvoiceType] else InvoiceType.SINGLE_TAX
                                                                      ^^^^^^^^^^^
NameError: name 'InvoiceType' is not defined

frontend:
s 200 in 74ms (next.js: 53ms, proxy.ts: 5ms, application-code: 15ms)
[browser] Detected `scroll-behavior: smooth` on the `<html>` element. To disable smooth scrolling during route transitions, add `data-scroll-behavior="smooth"` to your <html> element. Learn more: https://nextjs.org/docs/messages/missing-data-scroll-behavior
[browser] Failed to load initial page: Error: Unable to connect to backend server at http://127.0.0.1:8000/api/v1. Please ensure the backend service is running.
    at fetchWithAuth (src/lib/api.ts:54:13)
    at async fetchReconciliationResultsPage (src/features/sales/api/reconciliation.ts:107:15)
    at async usePagination.useEffect.fetchInitial (src/hooks/usePagination.ts:57:23)
  52 |   } catch (err: unknown) {
  53 |     if (err instanceof Error && (err.name === "TypeError" || err.message.includes("fetch") || err.mes...
> 54 |       throw new Error(`Unable to connect to backend server at ${API_BASE_URL}. Please ensure the back...
     |             ^
  55 |     }
  56 |     throw err;
  57 |   } (src/hooks/usePagination.ts:63:19)
