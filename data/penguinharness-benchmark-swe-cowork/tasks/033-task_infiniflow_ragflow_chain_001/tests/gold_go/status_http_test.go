package handler

import (
	"encoding/json"
	"github.com/gin-gonic/gin"
	"github.com/glebarez/sqlite"
	"gorm.io/gorm"
	"net/http/httptest"
	"ragflow/internal/dao"
	"ragflow/internal/entity"
	"ragflow/internal/service/dataset"
	"testing"
	"time"
)

func TestRepairCompilationStatusHTTP(t *testing.T) {
	db, err := gorm.Open(sqlite.Open(":memory:"), &gorm.Config{})
	if err != nil {
		t.Fatal(err)
	}
	sqlDB, _ := db.DB()
	sqlDB.SetMaxOpenConns(1)
	defer sqlDB.Close()
	if err = db.AutoMigrate(&entity.Knowledgebase{}, &entity.KnowledgeCompileDataset{}); err != nil {
		t.Fatal(err)
	}
	old := dao.DB
	dao.DB = db
	defer func() { dao.DB = old }()
	valid := "1"
	if err = db.Create(&entity.Knowledgebase{ID: "kb", TenantID: "owner", Name: "Dataset", Status: &valid, Permission: string(entity.TenantPermissionMe)}).Error; err != nil {
		t.Fatal(err)
	}
	gin.SetMode(gin.TestMode)
	g := gin.New()
	user := "owner"
	g.Use(func(c *gin.Context) {
		if user != "" {
			c.Set("user", &entity.User{ID: user})
		}
		c.Next()
	})
	h := NewDatasetsHandler(dataset.NewDatasetService(), nil)
	g.GET("/api/v1/datasets/:dataset_id/compilation/status", h.GetCompilationStatus)
	request := func() map[string]interface{} {
		t.Helper()
		w := httptest.NewRecorder()
		g.ServeHTTP(w, httptest.NewRequest("GET", "/api/v1/datasets/kb/compilation/status", nil))
		var body map[string]interface{}
		if err := json.Unmarshal(w.Body.Bytes(), &body); err != nil {
			t.Fatal(err)
		}
		return body
	}
	body := request()
	if body["code"] != float64(0) || body["data"].(map[string]interface{})["state"] != "idle" {
		t.Fatalf("idle reply=%+v", body)
	}
	now := time.Now().UTC().Truncate(time.Second)
	for _, state := range []string{"pending", "running", "completed"} {
		row := entity.KnowledgeCompileDataset{DatasetID: "kb", TenantID: "owner", State: state, Progress: .6, CurrentPhase: "writing", ProgressMsg: "stored", BacklogDocIDs: `[{"doc_id":"one"},{"doc_id":"two"}]`, InflightDocIDs: `[{"doc_id":"three"}]`, LastCompletedAt: &now, ErrorMsg: "retry this batch"}
		if err = db.Save(&row).Error; err != nil {
			t.Fatal(err)
		}
		body = request()
		data, ok := body["data"].(map[string]interface{})
		if !ok || body["code"] != float64(0) || data["state"] != state || data["backlog"] != float64(2) || data["inflight"] != float64(1) || data["progress"] != .6 || data["error"] != "retry this batch" || data["last_completed_at"] == nil {
			t.Fatalf("state reply=%+v", body)
		}
	}
	for _, denied := range []string{"outsider", ""} {
		user = denied
		body = request()
		if body["code"] == float64(0) {
			t.Fatalf("unauthorized user %q got %+v", user, body)
		}
	}
}
