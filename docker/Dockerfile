FROM dalibo/ldap2pg:5.7

LABEL project="georchestra.org"
LABEL app="ldap2pg"
LABEL org.opencontainers.image.authors="jeanpommier@pi-geosolutions.fr"

COPY  ./customize /georchestra-ldap2pg
RUN   pip3 install ldap3 ;\
      cp /georchestra-ldap2pg/config/ldap2pg.yml /etc/ldap2pg.yml ;\
      cp /georchestra-ldap2pg/hacks/format.py /usr/local/lib/python3.9/dist-packages/ldap2pg/format.py ;\
      cp /georchestra-ldap2pg/docker-entrypoint.d/* /docker-entrypoint.d/
# COPY ./hacks/format.py /usr/local/lib/python3.9/dist-packages/ldap2pg/format.py
# COPY ./scripts /georchestra-ldap2pg/scripts
# COPY ./config /georchestra-ldap2pg/scripts
# COPY ./docker/docker-entrypoint.d/* /docker-entrypoint.d/
