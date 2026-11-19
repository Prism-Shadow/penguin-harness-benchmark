package service

import (
	"context"
	"fmt"
	"ragflow/internal/dao"
	"ragflow/internal/ingestion/pipeline"
	"ragflow/internal/ingestion/testutil"
	servicepkg "ragflow/internal/service"
	"strings"
	"sync"
	"testing"
)

// Exercise the production sink, services and SQLite persistence together.
func TestRepairCompilerProgressLogLifecycle(t *testing.T) {
	db := testutil.SetupTestDB(t)
	defer testutil.ReplaceDBForTest(t, db)()
	_, _, docID, taskID := testutil.SeedTestData(t, db, testutil.WithPipelineID("flow-1"))
	ctx := context.Background()
	sink := newProgressSink(ctx, servicepkg.NewIngestionTaskService())
	sink.OnComponentTotal(ctx, taskID, 2)
	sink.OnComponentProgress(ctx, pipeline.ProgressEvent{TaskID: taskID, DocumentID: docID, Component: "Parser", Phase: 1, Message: "Parser Done"})
	var wg sync.WaitGroup
	for i := 0; i < 8; i++ {
		wg.Add(1)
		go func(i int) {
			defer wg.Done()
			sink.OnComponentMessage(ctx, taskID, docID, "Compiler", fmt.Sprintf("MAP batch %d", i))
		}(i)
	}
	wg.Wait()
	sink.OnComponentProgress(ctx, pipeline.ProgressEvent{TaskID: taskID, DocumentID: docID, Component: "Compiler", Phase: 1, Message: "Compiler Done"})
	doc, err := dao.NewDocumentDAO().GetByID(ctx, db, docID)
	if err != nil {
		t.Fatal(err)
	}
	if doc.Progress != 1 || doc.Run == nil || *doc.Run != "3" {
		t.Fatalf("final progress/state %+v", doc)
	}
	if doc.ProgressMsg == nil {
		t.Fatal("missing progress log")
	}
	log := *doc.ProgressMsg
	for _, msg := range []string{"Parser Done", "Compiler Done", "MAP batch 0", "MAP batch 7"} {
		if strings.Count(log, msg) != 1 {
			t.Fatalf("lost/duplicated %q: %s", msg, log)
		}
	}
	rows, err := dao.NewIngestionTaskLogDAO().ListLogsByTaskID(ctx, db, taskID)
	if err != nil || len(rows) != 2 {
		t.Fatalf("detail events changed component count: %d %v", len(rows), err)
	}
}
