#ifndef TLS_TRANSPORT_H
#define TLS_TRANSPORT_H

#include <stdbool.h>
#include <stddef.h>
#include <sys/types.h>

/* Thin TLS layer over an already-connected TCP socket, shared by the TCP and
   MQTT protocol modules. Compiled against OpenSSL when setup.py/Makefile
   define HAVE_OPENSSL; otherwise every call fails with a clear
   "not compiled in" error so callers degrade loudly, never silently.

   A tls_session_t wraps one SSL connection. The caller keeps ownership of the
   socket fd: tls_session_free() never closes it. Sessions are used from one
   thread at a time (the pools already guarantee per-slot single ownership). */

typedef struct tls_session tls_session_t;

/* True when OpenSSL support was compiled in. */
bool tls_available(void);

/* Perform a blocking TLS handshake over connected fd.
   sni_hostname sets SNI and, when verify_peer, the expected certificate name.
   verify_peer=false skips certificate/hostname checks (self-signed staging).
   Returns the session, or NULL with a human-readable reason in errbuf. */
tls_session_t* tls_session_create(int fd, const char* sni_hostname,
                                  bool verify_peer,
                                  char* errbuf, size_t errbuf_len);

/* Blocking full-length send. Returns len, or -1 on error. */
ssize_t tls_session_send(tls_session_t* session, const void* buf, size_t len);

/* Blocking read of up to len bytes. Returns >0 bytes read, 0 on orderly
   peer close, -1 on error. */
ssize_t tls_session_recv(tls_session_t* session, void* buf, size_t len);

/* Bytes already decrypted and buffered inside the session (readable without
   touching the socket). */
ssize_t tls_session_pending(tls_session_t* session);

/* Send close_notify (best effort) and free the session. fd stays open. */
void tls_session_free(tls_session_t* session);

#endif // TLS_TRANSPORT_H
