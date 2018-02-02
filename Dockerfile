FROM alpine:latest

MAINTAINER Edoardo Rosa <edoardo [dot] rosa90 [at] gmail [dot] com> (edoz90)

# == BASIC SOFTWARE ============================================================

RUN apk update && apk upgrade

# == ENV / PARAMS ==============================================================

ENV USR_USER http

# == USER / GROUP ==============================================================

RUN adduser -D -u 1000 -h /usr/share/nginx/ -g '${USR_USER}' ${USR_USER}

# == DEPENDENCIES ==============================================================

RUN apk --no-cache --update add \
        autoconf        \
        build-base      \
        ca-certificates \
        geoip           \
        geoip-dev       \
        gnupg           \
        libressl-dev    \
        libtool         \
        linux-headers   \
        pcre-dev        \
        pcre            \
        redis           \
        wget            \
        zlib-dev

# == APP =======================================================================

# Install nginx-mainline

USER ${USR_USER}

ENV NGINX_MAJOR 1
ENV NGINX_MINOR 13
ENV NGINX_BUILD 7
ENV NGINX_VERSION ${NGINX_MAJOR}.${NGINX_MINOR}.${NGINX_BUILD}
ENV NGINX_SOURCE https://nginx.org/download/nginx-${NGINX_VERSION}.tar.gz
ENV NGINX_PUBKEY https://nginx.org/keys/mdounin.key

ENV NAXSI_VERSION 0.55.3
ENV NAXSI_SOURCE https://github.com/nbs-system/naxsi/archive/${NAXSI_VERSION}/naxsi-${NAXSI_VERSION}.tar.gz

RUN mkdir -p /usr/share/nginx/sources
WORKDIR /usr/share/nginx/sources

RUN mkdir -p nginx-${NGINX_VERSION}
RUN wget ${NGINX_SOURCE} && wget ${NGINX_SOURCE}.asc && wget ${NGINX_PUBKEY}
RUN gpg --import $(basename ${NGINX_PUBKEY}) && gpg --verify nginx-${NGINX_VERSION}.tar.gz.asc
RUN tar -zxf nginx-${NGINX_VERSION}.tar.gz && \
    rm nginx-${NGINX_VERSION}.tar.gz.asc && \
    rm nginx-${NGINX_VERSION}.tar.gz

RUN wget ${NAXSI_SOURCE} && \
    tar -zxf naxsi-${NAXSI_VERSION}.tar.gz && \
    rm naxsi-${NAXSI_VERSION}.tar.gz

RUN cd nginx-${NGINX_VERSION} && \
    ./configure \
        --prefix=/etc/nginx                              \
        --conf-path=/etc/nginx/nginx.conf                \
        --sbin-path=/usr/bin/nginx                       \
        --pid-path=/run/nginx.pid                        \
        --lock-path=/run/lock/nginx.lock                 \
        --user=${USR_USER}                               \
        --group=${USR_USER}                              \
        --http-log-path=/var/log/nginx/access.log        \
        --error-log-path=stderr                          \
        --with-threads                                   \
        --with-file-aio                                  \
        --with-http_addition_module                      \
        --with-http_auth_request_module                  \
        --with-http_degradation_module                   \
        --with-http_geoip_module                         \
        --with-http_gunzip_module                        \
        --with-http_gzip_static_module                   \ 
        --with-http_secure_link_module                   \
        --with-http_ssl_module                           \
        --with-http_stub_status_module                   \
        --with-http_v2_module                            \
        --with-pcre-jit                                  \
        --add-module=../naxsi-${NAXSI_VERSION}/naxsi_src \
        && \
        make -j2 

# Change the user back to 'root'.
USER root

RUN cd nginx-${NGINX_VERSION} && \
    make install && \
    mkdir /etc/nginx/conf.d && \
    mkdir -p /usr/share/nginx/html/ && \
    install -m644 html/index.html /usr/share/nginx/html/ && \
    install -m644 html/50x.html /usr/share/nginx/html/ && \
    rm /etc/nginx/*.default && \
    install -Dm644 ../naxsi-${NAXSI_VERSION}/naxsi_config/naxsi_core.rules /etc/nginx/naxsi_core.rules

WORKDIR /usr/share/nginx

RUN apk add --update --no-cache uwsgi uwsgi-python3 uwsgi-logfile
# Copy default configurations
ADD dist/nginx.conf /etc/nginx/nginx.conf
ADD dist/conf.d/badbot.conf /etc/nginx/conf.d/badbot.conf

RUN mkdir -p /usr/share/nginx/html/dodohome
RUN chown ${USR_USER}:${USR_USER} -R /usr/share/nginx/html
RUN chown ${USR_USER}:${USR_USER} -R /var/log/uwsgi/
ADD dodohome /usr/share/nginx/html/dodohome/
ADD dist/dodohome.ini /etc/uwsgi/dodohome.ini
ADD dodohome.settings /usr/share/nginx/html/dodohome/dodohome.settings
RUN chown ${USR_USER}:${USR_USER} /etc/uwsgi/dodohome.ini
RUN pip3 install --no-cache-dir --upgrade pip
RUN pip3 install --no-cache-dir -r /usr/share/nginx/html/dodohome/requirements.txt

ADD dist/redis.conf /etc/redis.conf

# == LOGROTATE =================================================================

RUN apk add --update --no-cache logrotate

RUN mv /etc/periodic/daily/logrotate /etc/periodic/hourly/logrotate

# Add MYAPP-specific logrotate configuration.
ADD dist/logrotate.conf /etc/logrotate.d/nginx

# == RSYSLOG ===================================================================

RUN apk add --update --no-cache rsyslog
ADD dist/rsyslog.conf /etc/rsyslog.d/90.nginx.conf
 
# == SUPERVISORD ===============================================================

RUN apk add --update --no-cache supervisor
ADD dist/supervisord.ini /etc/supervisor.d/supervisord.ini

# == TOOLS (useful when inspecting the container) ==============================

RUN apk add --update --no-cache vim bash-completion tmux nginx-vim
    
# == CLEAN ================================================================

RUN apk del \
        libressl-dev    \
        linux-headers   \
        wget            \
        pcre-dev        \
        zlib-dev        \
        geoip-dev       \
        build-base      \
        autoconf        \
        libtool         \
        gnupg

RUN rm -r /usr/share/nginx/sources 

# == ENTRYPOINT ================================================================

EXPOSE 80

CMD ["/usr/bin/supervisord", "-c", "/etc/supervisord.conf"]
