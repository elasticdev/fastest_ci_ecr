FROM gear2000/nginx as build
MAINTAINER Gary Leong <gwleong@gmail.com>

RUN openssl req -newkey rsa:2048 -new -x509 -subj "/C=US/ST=California/L=SanFrancisco/O=Dis/CN=www.selfsigned.com" -days 1024 -nodes -out /tmp/cert.crt -keyout /tmp/cert.key

FROM nginx

COPY --from=build /tmp/cert.crt /etc/nginx/cert.crt
COPY --from=build /tmp/cert.key /etc/nginx/cert.key
#COPY cert.crt /etc/nginx/cert.crt
#COPY cert.key /etc/nginx/cert.key
COPY nginx-default.conf /etc/nginx/conf.d/default.conf
COPY run.sh /run.sh

#ENV REMOTE_URL="http://localhost:8080/"

CMD ["/run.sh"]
