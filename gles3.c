#define _GNU_SOURCE
#include <wayland-client.h>
#include <wayland-egl.h>
#include <EGL/egl.h>
#include <GLES3/gl3.h>

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include <time.h>
#include <signal.h>

static struct wl_display      *g_display      = NULL;
static struct wl_registry     *g_registry     = NULL;
static struct wl_compositor   *g_compositor   = NULL;
static struct wl_shell        *g_shell        = NULL;
static struct wl_surface      *g_surface      = NULL;
static struct wl_shell_surface *g_shell_surface = NULL;
static struct wl_egl_window   *g_egl_window   = NULL;

static EGLDisplay g_egl_display = EGL_NO_DISPLAY;
static EGLConfig  g_egl_config;
static EGLContext g_egl_context = EGL_NO_CONTEXT;
static EGLSurface g_egl_surface = EGL_NO_SURFACE;

static int g_width = 2000;
static int g_height = 1000;
static int g_running = 1;

static void handle_sigint(int sig) {
    (void)sig;
    g_running = 0;
}

/* ---------- Wayland globals ---------- */

static void registry_global(void *data,
                            struct wl_registry *registry,
                            uint32_t name,
                            const char *interface,
                            uint32_t version)
{
    (void)data;
    (void)version;

    if (strcmp(interface, "wl_compositor") == 0) {
        g_compositor = wl_registry_bind(registry, name, &wl_compositor_interface, 1);
    } else if (strcmp(interface, "wl_shell") == 0) {
        g_shell = wl_registry_bind(registry, name, &wl_shell_interface, 1);
    }
}

static void registry_global_remove(void *data,
                                   struct wl_registry *registry,
                                   uint32_t name)
{
    (void)data;
    (void)registry;
    (void)name;
}

static const struct wl_registry_listener g_registry_listener = {
    .global = registry_global,
    .global_remove = registry_global_remove
};

static void shell_surface_ping(void *data,
                               struct wl_shell_surface *shell_surface,
                               uint32_t serial)
{
    (void)data;
    wl_shell_surface_pong(shell_surface, serial);
}

static void shell_surface_configure(void *data,
                                    struct wl_shell_surface *shell_surface,
                                    uint32_t edges,
                                    int32_t width,
                                    int32_t height)
{
    (void)data;
    (void)shell_surface;
    (void)edges;
    if (width > 0 && height > 0) {
        g_width = width;
        g_height = height;
        if (g_egl_window) {
            wl_egl_window_resize(g_egl_window, g_width, g_height, 0, 0);
        }
    }
}

static void shell_surface_popup_done(void *data,
                                     struct wl_shell_surface *shell_surface)
{
    (void)data;
    (void)shell_surface;
}

static const struct wl_shell_surface_listener g_shell_surface_listener = {
    .ping = shell_surface_ping,
    .configure = shell_surface_configure,
    .popup_done = shell_surface_popup_done
};

/* ---------- EGL + GL helpers ---------- */

static void die(const char *msg) {
    fprintf(stderr, "FATAL: %s\n", msg);
    exit(EXIT_FAILURE);
}

static GLuint compile_shader(GLenum type, const char *src) {
    GLuint s = glCreateShader(type);
    glShaderSource(s, 1, &src, NULL);
    glCompileShader(s);
    GLint ok = 0;
    glGetShaderiv(s, GL_COMPILE_STATUS, &ok);
    if (!ok) {
        char log[1024];
        glGetShaderInfoLog(s, sizeof(log), NULL, log);
        fprintf(stderr, "Shader compile error: %s\n", log);
        die("compile_shader failed");
    }
    //printf("created shader %d from %s\n", type, src);
    return s;
}

static GLuint link_program(GLuint vs, GLuint fs) {
    GLuint p = glCreateProgram();
    glAttachShader(p, vs);
    glAttachShader(p, fs);
    glLinkProgram(p);
    GLint ok = 0;
    glGetProgramiv(p, GL_LINK_STATUS, &ok);
    if (!ok) {
        char log[1024];
        glGetProgramInfoLog(p, sizeof(log), NULL, log);
        fprintf(stderr, "Program link error: %s\n", log);
        die("link_program failed");
    }
    return p;
}

/* ---------- Simple math ---------- */

static void mat4_identity(float m[16]) {
    memset(m, 0, sizeof(float) * 16);
    m[0] = m[5] = m[10] = m[15] = 1.0f;
}

static void mat4_mul(float out[16], const float a[16], const float b[16]) {
    float r[16];
    for (int i = 0; i < 4; ++i) {
        for (int j = 0; j < 4; ++j) {
            r[i*4 + j] =
                a[i*4 + 0] * b[0*4 + j] +
                a[i*4 + 1] * b[1*4 + j] +
                a[i*4 + 2] * b[2*4 + j] +
                a[i*4 + 3] * b[3*4 + j];
        }
    }
    memcpy(out, r, sizeof(r));
}

static void mat4_perspective(float m[16], float fovy_rad, float aspect, float znear, float zfar) {
    float f = 1.0f / tanf(fovy_rad * 0.5f);
    memset(m, 0, sizeof(float) * 16);
    m[0] = f / aspect;
    m[5] = f;
    m[10] = (zfar + znear) / (znear - zfar);
    m[11] = -1.0f;
    m[14] = (2.0f * zfar * znear) / (znear - zfar);
}

static void mat4_translation(float m[16], float x, float y, float z) {
    mat4_identity(m);
    m[12] = x;
    m[13] = y;
    m[14] = z;
}

#if 0
static void mat4_translate(float m[16], float tx, float ty, float tz)
{
    float rot[16];
    float src[16];
    memcpy(src, m, sizeof src);
    mat4_translation(rot, tx, ty, tz);
    mat4_mul(m, rot, src);
}
#endif

static void mat4_rotation_y(float m[16], float angle_rad) {
    float c = cosf(angle_rad);
    float s = sinf(angle_rad);
    mat4_identity(m);
    m[0] = c;
    m[2] = -s;
    m[8] = s;
    m[10] = c;
}

static void mat4_rotation_x(float m[16], float angle_rad) {
    float c = cosf(angle_rad);
    float s = sinf(angle_rad);
    mat4_identity(m);
    m[5] = c;
    m[6] = s;
    m[9] = -s;
    m[10] = c;
}

struct framebuffer {
	int width;
	int height;
	GLuint id;
	GLuint texture;
	GLuint render;
};

void create_framebuffer(struct framebuffer *fb)
{
    glGenTextures(1, &fb->texture);
    glBindTexture(GL_TEXTURE_2D, fb->texture);
    glTexImage2D(GL_TEXTURE_2D, 0, GL_RGB, fb->width, fb->height, 0, GL_RGB, GL_UNSIGNED_BYTE, NULL);
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_NEAREST);
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_NEAREST);
    glBindTexture(GL_TEXTURE_2D, 0);

    glGenRenderbuffers(1, &fb->render);
    glBindRenderbuffer(GL_RENDERBUFFER, fb->render);
    glRenderbufferStorage(GL_RENDERBUFFER, GL_DEPTH24_STENCIL8, fb->width, fb->height);
    glBindRenderbuffer(GL_RENDERBUFFER, 0);

    glGenFramebuffers(1, &fb->id);
    glBindFramebuffer(GL_FRAMEBUFFER, fb->id);
    glFramebufferTexture2D(GL_FRAMEBUFFER, GL_COLOR_ATTACHMENT0, GL_TEXTURE_2D, fb->texture, 0);
    glFramebufferRenderbuffer(GL_FRAMEBUFFER, GL_DEPTH_STENCIL_ATTACHMENT, GL_RENDERBUFFER, fb->render);

    if(glCheckFramebufferStatus(GL_FRAMEBUFFER) != GL_FRAMEBUFFER_COMPLETE) {
	fprintf(stderr, "error: framebuffer incomplete");
    }

    glBindFramebuffer(GL_FRAMEBUFFER, 0);
}

GLuint create_program(const char *vs_src, const char *fs_src)
{
    GLuint vs = compile_shader(GL_VERTEX_SHADER, vs_src);
    GLuint fs = compile_shader(GL_FRAGMENT_SHADER, fs_src);
    GLuint prog = link_program(vs, fs);
    glDeleteShader(vs);
    glDeleteShader(fs);
    return prog;
}

/* ---------- Main ---------- */

#define CHECK_GL(x) if (glGetError() != GL_NO_ERROR) { fprintf(stderr, "failed %s: %d\n", #x, glGetError()); abort(); }

int main(void) {
    signal(SIGINT, handle_sigint);

    /* Wayland connection */
    g_display = wl_display_connect(NULL);
    if (!g_display) die("wl_display_connect failed");

    g_registry = wl_display_get_registry(g_display);
    wl_registry_add_listener(g_registry, &g_registry_listener, NULL);
    //wl_display_roundtrip(g_display);
    wl_display_dispatch(g_display);

    if (!g_compositor || !g_shell) die("missing compositor or shell");

    g_surface = wl_compositor_create_surface(g_compositor);
    if (!g_surface) die("wl_compositor_create_surface failed");

    g_shell_surface = wl_shell_get_shell_surface(g_shell, g_surface);
    if (!g_shell_surface) die("wl_shell_get_shell_surface failed");
    wl_shell_surface_add_listener(g_shell_surface, &g_shell_surface_listener, NULL);
    wl_shell_surface_set_toplevel(g_shell_surface);
    wl_shell_surface_set_title(g_shell_surface, "GLES3 Cube (Wayland)");

    g_egl_window = wl_egl_window_create(g_surface, g_width, g_height);
    if (!g_egl_window) die("wl_egl_window_create failed");

    /* EGL init */
    g_egl_display = eglGetDisplay((EGLNativeDisplayType)g_display);
    if (g_egl_display == EGL_NO_DISPLAY) die("eglGetDisplay failed");

    if (!eglInitialize(g_egl_display, NULL, NULL)) die("eglInitialize failed");

    EGLint cfg_attribs[] = {
        EGL_SURFACE_TYPE, EGL_WINDOW_BIT,
        EGL_RENDERABLE_TYPE, EGL_OPENGL_ES3_BIT,
        EGL_RED_SIZE,   8,
        EGL_GREEN_SIZE, 8,
        EGL_BLUE_SIZE,  8,
        EGL_ALPHA_SIZE, 8,
        EGL_DEPTH_SIZE, 24,
        EGL_NONE
    };

    EGLint num_cfg = 0;
    if (!eglChooseConfig(g_egl_display, cfg_attribs, &g_egl_config, 1, &num_cfg) || num_cfg < 1)
        die("eglChooseConfig failed");

    g_egl_surface = eglCreateWindowSurface(g_egl_display, g_egl_config,
                                           (EGLNativeWindowType)g_egl_window, NULL);
    if (g_egl_surface == EGL_NO_SURFACE) die("eglCreateWindowSurface failed");

    EGLint ctx_attribs[] = {
        EGL_CONTEXT_CLIENT_VERSION, 3,
        EGL_NONE
    };

    if (!eglBindAPI(EGL_OPENGL_ES_API)) die("eglBindAPI failed");

    g_egl_context = eglCreateContext(g_egl_display, g_egl_config,
                                     EGL_NO_CONTEXT, ctx_attribs);
    if (g_egl_context == EGL_NO_CONTEXT) die("eglCreateContext failed");

    if (!eglMakeCurrent(g_egl_display, g_egl_surface, g_egl_surface, g_egl_context))
        die("eglMakeCurrent failed");

    /* GL setup */
    const char *scene_vs =
        "#version 300 es\n"
        "layout(location = 0) in vec3 aPos;\n"
        "layout(location = 1) in vec3 aColor;\n"
        "out vec3 vColor;\n"
        "uniform mat4 mvp;\n"
        "void main() {\n"
        "  vColor = aColor;\n"
        "  gl_Position = mvp * vec4(aPos, 1.0);\n"
        "}\n";

    const char *scene_fs =
        "#version 300 es\n"
        "precision mediump float;\n"
        "in vec3 vColor;\n"
        "out vec4 fragColor;\n"
        "void main() {\n"
        "  fragColor = vec4(vColor, 1.0);\n"
        "}\n";

    const char *quad_vs =
	"#version 300 es\n"
	"layout (location = 0) in vec2 aPos;\n"
	"layout (location = 1) in vec2 aTexCoords;\n"
	"out vec2 TexCoords;\n"
	"void main()\n"
	"{\n"
    	"	gl_Position = vec4(aPos.x, aPos.y, 0.0, 1.0);\n"
    	"	TexCoords = aTexCoords;\n"
	"}";

    const char *quad_fs =
	"#version 300 es\n"
        "precision mediump float;\n"
	"out vec4 FragColor;\n"
	"in vec2 TexCoords;\n"
	"uniform sampler2D screenTexture;\n"
	"void main()\n"
	"{\n"
	"	FragColor = vec4(texture(screenTexture, TexCoords).rgb, 1);\n"
	"	vec4 tex = texture(screenTexture, TexCoords);\n"
    	"	if ((tex.r + tex.g + tex.b) < 0.0000001) discard;\n"
	"	FragColor = vec4(tex.rgb, 0.5);\n"
	"}";

    const char *quad_gray_fs =
	"#version 300 es\n"
        "precision mediump float;\n"
	"out vec4 FragColor;\n"
	"in vec2 TexCoords;\n"
	"uniform sampler2D screenTexture;\n"
	"void main()\n"
	"{\n"
	"	FragColor = texture(screenTexture, TexCoords);\n"
	"	float average = (FragColor.r + FragColor.g + FragColor.b) / 3.0;\n"
	//"       if (average < 0.000001) discard;\n"
    	"	FragColor = vec4(average, average, average, 1.0);\n"
	"}";

    GLuint scene_prog = create_program(scene_vs, scene_fs);
    GLuint quad_prog = create_program(quad_vs, quad_fs);
    GLuint gray_prog = create_program(quad_vs, quad_gray_fs);

    GLint loc_mvp = glGetUniformLocation(scene_prog, "mvp");

    // Cube vertices: position (x,y,z), color (r,g,b)
    float vertices[] = {
        // Front face
        -1, -1,  1,  1, 0, 0,
         1, -1,  1,  0, 1, 0,
         1,  1,  1,  0, 0, 1,
        -1,  1,  1,  1, 1, 0,
        // Back face
        -1, -1, -1,  1, 0, 1,
         1, -1, -1,  0, 1, 1,
         1,  1, -1,  1, 1, 1,
        -1,  1, -1,  0, 0, 0
    };

    GLushort indices[] = {
        // front
        0, 1, 2,  2, 3, 0,
        // right
        1, 5, 6,  6, 2, 1,
        // back
        5, 4, 7,  7, 6, 5,
        // left
        4, 0, 3,  3, 7, 4,
        // bottom
        4, 5, 1,  1, 0, 4,
        // top
        3, 2, 6,  6, 7, 3
    };

    float quadVertices[] = { // vertex attributes for a quad that fills the entire screen in Normalized Device Coordinates. NOTE that this plane is now much smaller and at the top of the screen
        // positions   // texCoords
        -1.0f,  1.0f,  0.0f, 1.0f,
        -1.0f,  -1.0f,  0.0f, 0.0f,
         1.0f,  1.0f,  1.0f, 1.0f,

        -1.0f,  -1.0f,  0.0f, 0.0f,
         1.0f,  -1.0f,  1.0f, 0.0f,
         1.0f,  1.0f,  1.0f, 1.0f
    };

    for (int i = 0; i < sizeof vertices / sizeof *vertices; i++) {
	    vertices[i] /= 2.0f;
    }

    GLuint vao, vbo, ebo;
    glGenVertexArrays(1, &vao);
    glGenBuffers(1, &vbo);
    glGenBuffers(1, &ebo);
    glBindVertexArray(vao);
    glBindBuffer(GL_ARRAY_BUFFER, vbo);
    glBufferData(GL_ARRAY_BUFFER, sizeof(vertices), vertices, GL_STATIC_DRAW);
    glBindBuffer(GL_ELEMENT_ARRAY_BUFFER, ebo);
    glBufferData(GL_ELEMENT_ARRAY_BUFFER, sizeof(indices), indices, GL_STATIC_DRAW);
    glEnableVertexAttribArray(0);
    glVertexAttribPointer(0, 3, GL_FLOAT, GL_FALSE, 6 * sizeof(float), (void*)0);
    glEnableVertexAttribArray(1);
    glVertexAttribPointer(1, 3, GL_FLOAT, GL_FALSE, 6 * sizeof(float), (void*)(3 * sizeof(float)));

    GLuint quad_vao, quad_vbo;
    glGenVertexArrays(1, &quad_vao);
    glGenBuffers(1, &quad_vbo);
    glBindVertexArray(quad_vao);
    glBindBuffer(GL_ARRAY_BUFFER, quad_vbo);
    glBufferData(GL_ARRAY_BUFFER, sizeof(quadVertices), &quadVertices, GL_STATIC_DRAW);
    glEnableVertexAttribArray(0);
    glVertexAttribPointer(0, 2, GL_FLOAT, GL_FALSE, 4 * sizeof(float), (void*)0);
    glEnableVertexAttribArray(1);
    glVertexAttribPointer(1, 2, GL_FLOAT, GL_FALSE, 4 * sizeof(float), (void*)(2 * sizeof(float)));

    glBindVertexArray(0);

    glEnable(GL_DEPTH_TEST);
    glEnable(GL_CULL_FACE);
    glCullFace(GL_BACK);

    struct timespec start_ts;
    clock_gettime(CLOCK_MONOTONIC, &start_ts);

    struct framebuffer full_scene = {g_width, g_height};
    create_framebuffer(&full_scene);

    struct framebuffer backlight = {36, 22};
    create_framebuffer(&backlight);

    while (g_running) {
        while (wl_display_dispatch_pending(g_display) != -1) {
            break;
        }

        struct timespec now;
        clock_gettime(CLOCK_MONOTONIC, &now);
        double t = (now.tv_sec - start_ts.tv_sec) +
                   (now.tv_nsec - start_ts.tv_nsec) / 1e9;

	// draw scene
	glBindFramebuffer(GL_FRAMEBUFFER, full_scene.id);
        glViewport(0, 0, full_scene.width, full_scene.height);
        glClearColor(0, 0, 0, 1.0f);
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT);

        float proj[16], view[16], model[16], mv[16], mvp[16], rx[16], ry[16];

        mat4_perspective(proj, (float)M_PI/4, (float)g_width / (float)g_height, 0.1f, 100.0f);
        mat4_translation(view, 0.0f, 0.0f, -5.0f);
        mat4_rotation_y(ry, -(float)t*M_PI/5/2);
        mat4_rotation_x(rx, -(float)t*M_PI/2/5/2);
	mat4_mul(model, rx, ry);
        mat4_mul(mv, model, view);
        mat4_mul(mvp, mv, proj);

        glUseProgram(scene_prog);
        glUniformMatrix4fv(loc_mvp, 1, GL_FALSE, mvp);
        glBindVertexArray(vao);
        glDrawElements(GL_TRIANGLES, sizeof(indices) / sizeof(indices[0]), GL_UNSIGNED_SHORT, 0);
        glBindVertexArray(0);

	// draw backlight from full scene
#define GL_CONSERVATIVE_RASTERIZATION_NV  0x9346
	//glEnable(GL_CONSERVATIVE_RASTERIZATION_NV);
	//CHECK_GL(GL_CONSERVATIVE_RASTERIZATION_NV);
	glBindFramebuffer(GL_FRAMEBUFFER, backlight.id);
        glViewport(-2, -2, backlight.width+4, backlight.height+4);
	glClearColor(0, 0, 0, 1.0f);
	glClear(GL_COLOR_BUFFER_BIT);

	glUseProgram(gray_prog);
        glBindVertexArray(quad_vao);
	glDisable(GL_DEPTH_TEST);
	glBindTexture(GL_TEXTURE_2D, full_scene.texture);
	glDrawArrays(GL_TRIANGLES, 0, 6);
        glBindVertexArray(0);

	// draw display from full scene
	glBindFramebuffer(GL_FRAMEBUFFER, 0); // back to default
        glViewport(0, 0, g_width, g_height);
	glClearColor(0, 0, 0, 1.0f);
	glClear(GL_COLOR_BUFFER_BIT);

	glUseProgram(quad_prog);
        glBindVertexArray(quad_vao);
	glDisable(GL_DEPTH_TEST);

	glBindTexture(GL_TEXTURE_2D, backlight.texture);
	glDrawArrays(GL_TRIANGLES, 0, 6);

#if 1
	glEnable(GL_BLEND);
	glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA);

	glBindTexture(GL_TEXTURE_2D, full_scene.texture);
	glDrawArrays(GL_TRIANGLES, 0, 6);
#endif
        glBindVertexArray(0);
	//usleep(16000);

        eglSwapBuffers(g_egl_display, g_egl_surface);
    }

    /* Cleanup */
    glDeleteTextures(1, &full_scene.texture);
    glDeleteRenderbuffers(1, &full_scene.render);
    glDeleteFramebuffers(1, &full_scene.id);
    glDeleteBuffers(1, &ebo);
    glDeleteBuffers(1, &vbo);
    glDeleteVertexArrays(1, &vao);
    glDeleteProgram(scene_prog);
    glDeleteProgram(quad_prog);

    eglMakeCurrent(g_egl_display, EGL_NO_SURFACE, EGL_NO_SURFACE, EGL_NO_CONTEXT);
    eglDestroySurface(g_egl_display, g_egl_surface);
    eglDestroyContext(g_egl_display, g_egl_context);
    eglTerminate(g_egl_display);

    if (g_egl_window) wl_egl_window_destroy(g_egl_window);
    if (g_shell_surface) wl_shell_surface_destroy(g_shell_surface);
    if (g_surface) wl_surface_destroy(g_surface);
    if (g_compositor) wl_compositor_destroy(g_compositor);
    if (g_shell) wl_shell_destroy(g_shell);
    if (g_registry) wl_registry_destroy(g_registry);
    if (g_display) wl_display_disconnect(g_display);
    printf("\nGL shutdown\n");

    return 0;
}

