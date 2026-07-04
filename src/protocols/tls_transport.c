#include "tls_transport.h"

#include <stdio.h>
#include <string.h>

#ifdef HAVE_OPENSSL

#include <openssl/ssl.h>
#include <openssl/err.h>
#include <openssl/x509v3.h>
#include <pthread.h>
#include <stdlib.h>

struct tls_session {
    SSL* ssl;
};

/* One process-wide client context; OpenSSL >= 1.1 self-initializes and the
   context is thread-safe for creating sessions. */
static SSL_CTX* tls_ctx = NULL;
static pthread_once_t tls_ctx_once = PTHREAD_ONCE_INIT;

static void tls_ctx_init(void) {
    const SSL_METHOD* method = TLS_client_method();
    tls_ctx = SSL_CTX_new(method);
    if (!tls_ctx) return;
    /* TLS 1.2 minimum; trust the platform default CA store for verification. */
    SSL_CTX_set_min_proto_version(tls_ctx, TLS1_2_VERSION);
    SSL_CTX_set_default_verify_paths(tls_ctx);
}

/* Copy the most recent OpenSSL error (or fallback) into errbuf. */
static void tls_fill_error(char* errbuf, size_t errbuf_len, const char* fallback) {
    if (!errbuf || errbuf_len == 0) return;
    unsigned long err = ERR_peek_last_error();
    if (err != 0) {
        char detail[256];
        ERR_error_string_n(err, detail, sizeof(detail));
        snprintf(errbuf, errbuf_len, "%s: %s", fallback, detail);
    } else {
        snprintf(errbuf, errbuf_len, "%s", fallback);
    }
    ERR_clear_error();
}

bool tls_available(void) {
    return true;
}

tls_session_t* tls_session_create(int fd, const char* sni_hostname,
                                  bool verify_peer,
                                  char* errbuf, size_t errbuf_len) {
    pthread_once(&tls_ctx_once, tls_ctx_init);
    if (!tls_ctx) {
        tls_fill_error(errbuf, errbuf_len, "Failed to create TLS context");
        return NULL;
    }

    tls_session_t* session = calloc(1, sizeof(tls_session_t));
    if (!session) {
        snprintf(errbuf, errbuf_len, "Out of memory (TLS session)");
        return NULL;
    }

    session->ssl = SSL_new(tls_ctx);
    if (!session->ssl) {
        tls_fill_error(errbuf, errbuf_len, "Failed to create TLS session");
        free(session);
        return NULL;
    }

    if (sni_hostname && sni_hostname[0]) {
        SSL_set_tlsext_host_name(session->ssl, sni_hostname);
        if (verify_peer) {
            /* Match the certificate against the hostname we dialed. */
            SSL_set1_host(session->ssl, sni_hostname);
        }
    }
    SSL_set_verify(session->ssl, verify_peer ? SSL_VERIFY_PEER : SSL_VERIFY_NONE, NULL);

    if (SSL_set_fd(session->ssl, fd) != 1) {
        tls_fill_error(errbuf, errbuf_len, "Failed to bind TLS session to socket");
        SSL_free(session->ssl);
        free(session);
        return NULL;
    }

    ERR_clear_error();
    if (SSL_connect(session->ssl) != 1) {
        long vr = SSL_get_verify_result(session->ssl);
        if (verify_peer && vr != X509_V_OK) {
            snprintf(errbuf, errbuf_len, "TLS certificate verification failed: %s",
                     X509_verify_cert_error_string(vr));
            ERR_clear_error();
        } else {
            tls_fill_error(errbuf, errbuf_len, "TLS handshake failed");
        }
        SSL_free(session->ssl);
        free(session);
        return NULL;
    }

    return session;
}

ssize_t tls_session_send(tls_session_t* session, const void* buf, size_t len) {
    if (!session || !session->ssl || (!buf && len > 0)) return -1;

    size_t total = 0;
    while (total < len) {
        ERR_clear_error();
        int n = SSL_write(session->ssl, (const char*)buf + total, (int)(len - total));
        if (n <= 0) {
            return -1;
        }
        total += (size_t)n;
    }
    return (ssize_t)total;
}

ssize_t tls_session_recv(tls_session_t* session, void* buf, size_t len) {
    if (!session || !session->ssl || !buf || len == 0) return -1;

    ERR_clear_error();
    int n = SSL_read(session->ssl, buf, (int)len);
    if (n > 0) return (ssize_t)n;

    int err = SSL_get_error(session->ssl, n);
    if (err == SSL_ERROR_ZERO_RETURN) {
        return 0; /* orderly TLS shutdown by the peer */
    }
    return -1;
}

ssize_t tls_session_pending(tls_session_t* session) {
    if (!session || !session->ssl) return 0;
    return (ssize_t)SSL_pending(session->ssl);
}

void tls_session_free(tls_session_t* session) {
    if (!session) return;
    if (session->ssl) {
        /* Best-effort close_notify; a single non-blocking-ish attempt is fine. */
        SSL_shutdown(session->ssl);
        SSL_free(session->ssl);
    }
    free(session);
}

#else /* !HAVE_OPENSSL: loud stubs so TLS requests never degrade silently */

bool tls_available(void) {
    return false;
}

tls_session_t* tls_session_create(int fd, const char* sni_hostname,
                                  bool verify_peer,
                                  char* errbuf, size_t errbuf_len) {
    (void)fd; (void)sni_hostname; (void)verify_peer;
    if (errbuf && errbuf_len > 0) {
        snprintf(errbuf, errbuf_len,
                 "TLS support not compiled in (OpenSSL not found at build time)");
    }
    return NULL;
}

ssize_t tls_session_send(tls_session_t* session, const void* buf, size_t len) {
    (void)session; (void)buf; (void)len;
    return -1;
}

ssize_t tls_session_recv(tls_session_t* session, void* buf, size_t len) {
    (void)session; (void)buf; (void)len;
    return -1;
}

ssize_t tls_session_pending(tls_session_t* session) {
    (void)session;
    return 0;
}

void tls_session_free(tls_session_t* session) {
    (void)session;
}

#endif /* HAVE_OPENSSL */
