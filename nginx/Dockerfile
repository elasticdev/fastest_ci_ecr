#FROM gear2000/nginx as build
#FROM ubuntu as build
FROM ubuntu/16:04 as build
MAINTAINER Gary Leong <gwleong@gmail.com>

RUN apt-get update && apt-get install openssl -y
RUN openssl req -newkey rsa:2048 -new -x509 -subj "/C=US/ST=California/L=SanFrancisco/O=Dis/CN=www.selfsigned.com" -days 1024 -nodes -out /tmp/cert.crt -keyout /tmp/cert.key

FROM nginx

COPY --from=build /tmp/cert.crt /etc/nginx/cert.crt
COPY --from=build /tmp/cert.key /etc/nginx/cert.key

COPY default.conf /etc/nginx/conf.d/default.conf

EXPOSE 443

CMD ["nginx", "-g", "daemon off;"]
