FROM gear2000/nginx
MAINTAINER Gary Leong <gwleong@gmail.com>

RUN apt-get update && apt-get install -y vim ack-grep 
RUN apt-get clean && rm -rf /var/cache/apt/archives/*

RUN ln -sf /dev/stdout /var/log/nginx/access.log && ln -sf /dev/stderr /var/log/nginx/error.log

RUN rm -rf /etc/nginx/sites-enabled/* 
ADD sites-enabled/ /etc/nginx/sites-enabled/

ADD snippets/ /etc/nginx/snippets/
RUN mkdir -p /etc/ssl/certs && mkdir -p /etc/ssl/private
RUN rm -rf /etc/nginx/nginx.conf
ADD nginx.conf /etc/nginx/nginx.conf

RUN openssl req -newkey rsa:2048 -new -x509 -subj "/C=US/ST=California/L=SanFrancisco/O=Dis/CN=www.selfsigned.com" -days 1024 -nodes -out /etc/ssl/certs/nginx.crt -keyout /etc/ssl/private/nginx.key 
RUN openssl dhparam -out /etc/ssl/certs/dhparam.pem 2048

EXPOSE 443

CMD ["nginx", "-g", "daemon off;"]

