# 🧠 MathMentor IA: El Tutor Personal de Matemáticas (con Gamificación)

**MathMentor IA** es una aplicación educativa de vanguardia diseñada para **transformar la manera en que los estudiantes abordan las matemáticas**, haciendo el aprendizaje más efectivo y atractivo. Utilizando el poder de la Inteligencia Artificial, la plataforma ofrece práctica altamente personalizada, correcciones detalladas y un **sistema de puntuación motivacional** para incentivar la constancia y el esfuerzo.

---

## ✨ Características Principales

* **Generación de Ejercicios Personalizados:** La IA genera problemas matemáticos directamente basados en el contenido de libros de texto específicos y en los temas seleccionados.
* **Corrección Inteligente con Feedback Didáctico:** No solo verifica la respuesta, sino que analiza la ejecución, detecta errores de procedimiento o conceptuales y explica detalladamente dónde y por qué se cometieron los fallos, actuando como un verdadero tutor.
* **Sistema de Puntuación (Gamificación):** Se integra un sistema de puntos para motivar al estudiante a través de la recompensa del esfuerzo y la precisión.
* **Base de Conocimiento Curricular (RAG):** Los libros en PDF se procesan para construir una base de conocimiento robusta y contextualizada, garantizando que los ejercicios y las explicaciones estén perfectamente alineados con el material de estudio.

---

## 🚀 Innovación: Sistema de Puntuación Dinámico

Se implementará un sistema de puntuación para motivar a los estudiantes a centrarse tanto en el proceso como en el resultado final:

| Criterio de Puntuación | Descripción | Puntos (Ejemplo) |
| :--- | :--- | :--- |
| **Resultado Correcto** | Se otorga cuando la respuesta final numérica o conceptual es completamente correcta. | **+10 Puntos** |
| **Desarrollo Correcto** | Se otorga cuando el estudiante ha seguido la metodología correcta o ha demostrado comprensión de los pasos principales, aunque haya cometido un error de cálculo menor en el camino. | **+5 Puntos** |
| **Corrección y Esfuerzo** | Se otorga si el estudiante, tras recibir el *feedback* didáctico de la IA, intenta nuevamente el ejercicio y lo resuelve correctamente. | **+3 Puntos** |
| **Racha de Aciertos** | Puntos extra por completar una serie de ejercicios seguidos de forma exitosa. | **Bonificación** |

El alumno podrá visualizar un **marcador personal** con su progreso y puntos acumulados, fomentando la dedicación continua.

---

## 🛠️ Modos de Uso y Funcionalidades

### 🔐 Sistema de Autenticación y Roles

La aplicación cuenta con un sistema de inicio de sesión seguro con dos roles definidos:

1.  **Administrador:** Acceso a la gestión de contenido, configuración del sistema y monitorización de uso.
2.  **Alumno:** Acceso a la práctica, el estudio y el sistema de puntuación.

### 📚 Funcionalidades para el Administrador

* **Registro de Libros (PDF):** Formulario para subir PDFs, informando el **Curso**, **Título** y **Materia**.
* **Procesamiento y RAG:** La IA extrae automáticamente los **Temas** disponibles del PDF y añade su contenido a la base de datos RAG para contextualizar los ejercicios.
* **Gestión de Motores de IA:** Panel para configurar y seleccionar el motor de IA para la generación y corrección.
    * **Motores Disponibles:** **OpenAI, DeepSeek y Ollama.**
    * **Parámetros Configurables:** Permite establecer claves API, *modelos* y otros parámetros técnicos.

### 🧑‍🎓 Flujo de Trabajo para el Alumno

1.  **Selección de Contexto:** El alumno selecciona su **Curso** y el **Tema** + **Sub tema** específicos a practicar, extraído por la IA de los libros cargados.
2.  **Generación de Ejercicio:** La IA (utilizando el motor configurado y la información del RAG) **propone un ejercicio** relevante al tema y nivel.
3.  **Resolución y Envío:** El alumno resuelve el ejercicio.
4.  **Corrección, Feedback y Puntuación:**
    * La IA **corrige** la solución y el procedimiento.
    * Asigna los **Puntos** según la precisión del resultado y el desarrollo.
    * Si hay errores, proporciona una **explicación didáctica** indicando el fallo conceptual y cómo corregirlo, permitiendo al alumno volver a intentarlo y ganar puntos extra por esfuerzo.

---

## ⚙️ Arquitectura Técnica

| Componente | Tecnología | Propósito |
| :--- | :--- | :--- |
| **Backend** | **Flask** (Python) | Lógica de la aplicación, gestión de roles, API de IA, archivos y sistema de puntuación. |
| **Base de Datos** | **PostgreSQL** | Almacenamiento de usuarios, libros, puntuaciones, y **vectores para el RAG**. |
| **Despliegue** | **Docker Compose** | Contenerización y orquestación de la aplicación Flask y PostgreSQL. |
| **Inteligencia Artificial** | **OpenAI, DeepSeek, Ollama** | Generación de problemas, procesamiento de documentos, corrección y *feedback* personalizado. |
