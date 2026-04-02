print("de rucula")

###
# BORRAR ESTO PQ ME DIO PAJA METERLO EN OTRO LADO JE
###
# comandos que use para probar

# docker build -t servidor-hit2 .

# docker run -d \
#   --name servidor-concurrente \
#   -p 8080:8080 \
#   -v /var/run/docker.sock:/var/run/docker.sock \
#   servidor-tp-hit2
  
# docker logs -f servidor-concurrente


# en otra terminal

# manda 20 peticiones al toque roque esto
# for i in {1..20}; do
#   curl -s -X POST http://localhost:8080/getRemoteTask \
#        -H "Content-Type: application/json" \
#        -d '{"servicio": "texto", "payload": {"texto": "Mensaje de prueba '$i'"}, "lamport_ts": '$i'}' &
# done