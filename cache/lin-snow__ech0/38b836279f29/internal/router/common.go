package router

import "github.com/lin-snow/ech0/internal/handler"

// setupCommonRoutes 设置普通路由
func setupCommonRoutes(appRouterGroup *AppRouterGroup, h *handler.Bundle) {
	// Public
	appRouterGroup.PublicRouterGroup.GET("/heatmap", h.CommonHandler.GetHeatMap())
	appRouterGroup.PublicRouterGroup.GET("/hello", h.CommonHandler.HelloEch0())
	appRouterGroup.PublicRouterGroup.GET("/backup/export", h.BackupHandler.ExportBackup())
	appRouterGroup.PublicRouterGroup.GET("/website/title", h.CommonHandler.GetWebsiteTitle())
}
