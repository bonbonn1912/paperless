import { Routes } from '@angular/router';
import { authGuard } from './core/guards/auth.guard';
import { LayoutComponent } from './features/layout/layout.component';
import { LoginComponent } from './features/auth/login.component';
import { LibraryComponent } from './features/documents/library.component';
import { DocumentViewerComponent } from './features/documents/viewer.component';
import { ReviewComponent } from './features/review/review.component';
import { BatchUploadComponent } from './features/batch-upload/batch-upload.component';
import { CameraCaptureComponent } from './features/camera/camera-capture.component';
import { SettingsComponent } from './features/settings/settings.component';

export const routes: Routes = [
  {
    path: 'login',
    component: LoginComponent
  },
  {
    path: '',
    component: LayoutComponent,
    canActivate: [authGuard],
    children: [
      {
        path: '',
        pathMatch: 'full',
        redirectTo: 'documents'
      },
      {
        path: 'documents',
        component: LibraryComponent
      },
      {
        path: 'documents/:id',
        component: DocumentViewerComponent
      },
      {
        path: 'review',
        component: ReviewComponent
      },
      {
        path: 'batch-upload',
        component: BatchUploadComponent
      },
      {
        path: 'camera',
        component: CameraCaptureComponent
      },
      {
        path: 'settings',
        component: SettingsComponent
      }
    ]
  },
  {
    path: '**',
    redirectTo: 'documents'
  }
];
