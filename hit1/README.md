Implemente un servidor que resuelva “tareas genéricas” o “pre-compiladas”. Para ello, hay un conjunto de acciones de diseño y arquitectura que deben respetarse:

### SERVIDOR
* Desarrollar el servidor utilizando tecnología HTTP.
* El servidor debe ser contenerizado y alojado en un host con Docker instalado.
* Permanecerá receptivo a nuevas solicitudes del cliente, exponiendo métodos para interactuar.
* Debe incluir un método llamado ejecutarTareaRemota() asociado a un endpoint (getRemoteTask()) para procesar tareas genéricas enviadas por el cliente.
* Los parámetros de las tareas serán recibidos a través de solicitudes HTTP GET/POST, utilizando una estructura JSON.
* Durante la ejecución, el servidor levantará temporalmente un “servicio tarea” como un contenedor Docker.
* Una vez en funcionamiento, se comunicará con el “servicio tarea” para ejecutar la tarea con los parámetros proporcionados.
* Esperará los resultados de la tarea y los enviará de vuelta al cliente.

### SERVICIO TAREA
* Establecer un servicio de escucha utilizando un servidor web.
* Implementar la tarea de procesamiento denominada ejecutarTarea().
* Configurar el servicio para recibir los parámetros de entrada en formato JSON.
* Empaquetar la solución como una imagen Docker para facilitar la distribución y el despliegue.
* Publicar la solución en el registro de Docker Hub, ya sea público o privado, para que esté disponible para su uso y colaboración.

### CLIENTE
* Utilizar una solicitud HTTP GET/POST para comunicarse con el servidor.
* Enviar los parámetros necesarios para la tarea en formato JSON, incluyendo:
    * El cálculo a realizar.
    * Los parámetros específicos requeridos para la tarea.
    * Datos adicionales necesarios para el procesamiento.
    * La imagen Docker que contiene la solución de la tarea.