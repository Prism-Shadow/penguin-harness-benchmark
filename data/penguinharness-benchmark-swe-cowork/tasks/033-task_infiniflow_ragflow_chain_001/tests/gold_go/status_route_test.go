package router

import (
	"github.com/gin-gonic/gin"
	"net/http/httptest"
	"ragflow/internal/common"
	"ragflow/internal/handler"
	"testing"
)

func TestRepairCompilationStatusRegisteredAndProtected(t *testing.T) {
	if err := common.InitLogger("info", common.FileOutput{}, ""); err != nil {
		t.Fatal(err)
	}
	gin.SetMode(gin.TestMode)
	g := gin.New()
	r := &Router{authHandler: &handler.AuthHandler{}}
	r.Setup(g)
	w := httptest.NewRecorder()
	g.ServeHTTP(w, httptest.NewRequest("GET", "/api/v1/datasets/kb/compilation/status", nil))
	if w.Code != 401 {
		t.Fatalf("production route missing/auth bypass: %d %s", w.Code, w.Body.String())
	}
}
