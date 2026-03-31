Despliegue 2 o más instancias del servidor del Hit #1 detrás de un balanceador de carga (puede usar nginx, HAProxy o un load balancer en la nube).

Implemente un mecanismo de elección de líder utilizando el algoritmo Bully para que uno de los nodos actúe como coordinador del sistema. El coordinador será responsable de:
* Asignar tareas entrantes a los nodos workers disponibles.
* Mantener el registro de estado de cada nodo.
* Si el líder/coordinador se cae (simúlelo matando el proceso), otro nodo debe detectar la caída y tomar el control automáticamente mediante una nueva elección.

Documente en su informe: el diagrama de secuencia de una elección de líder, el tiempo de recuperación ante una caída del coordinador, y cómo se redistribuyen las tareas pendientes.
