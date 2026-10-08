-- MySQL dump 10.13  Distrib 8.0.41, for Win64 (x86_64)
--
-- Host: 127.0.0.1    Database: constructora
-- ------------------------------------------------------
-- Server version	8.0.41

/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
/*!40101 SET @OLD_CHARACTER_SET_RESULTS=@@CHARACTER_SET_RESULTS */;
/*!40101 SET @OLD_COLLATION_CONNECTION=@@COLLATION_CONNECTION */;
/*!50503 SET NAMES utf8 */;
/*!40103 SET @OLD_TIME_ZONE=@@TIME_ZONE */;
/*!40103 SET TIME_ZONE='+00:00' */;
/*!40014 SET @OLD_UNIQUE_CHECKS=@@UNIQUE_CHECKS, UNIQUE_CHECKS=0 */;
/*!40014 SET @OLD_FOREIGN_KEY_CHECKS=@@FOREIGN_KEY_CHECKS, FOREIGN_KEY_CHECKS=0 */;
/*!40101 SET @OLD_SQL_MODE=@@SQL_MODE, SQL_MODE='NO_AUTO_VALUE_ON_ZERO' */;
/*!40111 SET @OLD_SQL_NOTES=@@SQL_NOTES, SQL_NOTES=0 */;

--
-- Table structure for table `auth_group`
--

DROP TABLE IF EXISTS `auth_group`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `auth_group` (
  `id` int NOT NULL AUTO_INCREMENT,
  `name` varchar(150) NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `name` (`name`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `auth_group`
--

LOCK TABLES `auth_group` WRITE;
/*!40000 ALTER TABLE `auth_group` DISABLE KEYS */;
/*!40000 ALTER TABLE `auth_group` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `auth_group_permissions`
--

DROP TABLE IF EXISTS `auth_group_permissions`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `auth_group_permissions` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `group_id` int NOT NULL,
  `permission_id` int NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `auth_group_permissions_group_id_permission_id_0cd325b0_uniq` (`group_id`,`permission_id`),
  KEY `auth_group_permissio_permission_id_84c5c92e_fk_auth_perm` (`permission_id`),
  CONSTRAINT `auth_group_permissio_permission_id_84c5c92e_fk_auth_perm` FOREIGN KEY (`permission_id`) REFERENCES `auth_permission` (`id`),
  CONSTRAINT `auth_group_permissions_group_id_b120cbf9_fk_auth_group_id` FOREIGN KEY (`group_id`) REFERENCES `auth_group` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `auth_group_permissions`
--

LOCK TABLES `auth_group_permissions` WRITE;
/*!40000 ALTER TABLE `auth_group_permissions` DISABLE KEYS */;
/*!40000 ALTER TABLE `auth_group_permissions` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `auth_permission`
--

DROP TABLE IF EXISTS `auth_permission`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `auth_permission` (
  `id` int NOT NULL AUTO_INCREMENT,
  `name` varchar(255) NOT NULL,
  `content_type_id` int NOT NULL,
  `codename` varchar(100) NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `auth_permission_content_type_id_codename_01ab375a_uniq` (`content_type_id`,`codename`),
  CONSTRAINT `auth_permission_content_type_id_2f476e4b_fk_django_co` FOREIGN KEY (`content_type_id`) REFERENCES `django_content_type` (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=49 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `auth_permission`
--

LOCK TABLES `auth_permission` WRITE;
/*!40000 ALTER TABLE `auth_permission` DISABLE KEYS */;
INSERT INTO `auth_permission` VALUES (1,'Can add log entry',1,'add_logentry'),(2,'Can change log entry',1,'change_logentry'),(3,'Can delete log entry',1,'delete_logentry'),(4,'Can view log entry',1,'view_logentry'),(5,'Can add permission',2,'add_permission'),(6,'Can change permission',2,'change_permission'),(7,'Can delete permission',2,'delete_permission'),(8,'Can view permission',2,'view_permission'),(9,'Can add group',3,'add_group'),(10,'Can change group',3,'change_group'),(11,'Can delete group',3,'delete_group'),(12,'Can view group',3,'view_group'),(13,'Can add user',4,'add_user'),(14,'Can change user',4,'change_user'),(15,'Can delete user',4,'delete_user'),(16,'Can view user',4,'view_user'),(17,'Can add content type',5,'add_contenttype'),(18,'Can change content type',5,'change_contenttype'),(19,'Can delete content type',5,'delete_contenttype'),(20,'Can view content type',5,'view_contenttype'),(21,'Can add session',6,'add_session'),(22,'Can change session',6,'change_session'),(23,'Can delete session',6,'delete_session'),(24,'Can view session',6,'view_session'),(25,'Can add Cuadrilla',7,'add_cuadrilla'),(26,'Can change Cuadrilla',7,'change_cuadrilla'),(27,'Can delete Cuadrilla',7,'delete_cuadrilla'),(28,'Can view Cuadrilla',7,'view_cuadrilla'),(29,'Can add Proyecto',8,'add_proyecto'),(30,'Can change Proyecto',8,'change_proyecto'),(31,'Can delete Proyecto',8,'delete_proyecto'),(32,'Can view Proyecto',8,'view_proyecto'),(33,'Can add Integrante',9,'add_integrante'),(34,'Can change Integrante',9,'change_integrante'),(35,'Can delete Integrante',9,'delete_integrante'),(36,'Can view Integrante',9,'view_integrante'),(37,'Can add Cambio de cuadrilla',10,'add_cambiocuadrilla'),(38,'Can change Cambio de cuadrilla',10,'change_cambiocuadrilla'),(39,'Can delete Cambio de cuadrilla',10,'delete_cambiocuadrilla'),(40,'Can view Cambio de cuadrilla',10,'view_cambiocuadrilla'),(41,'Can add Solicitud de Reasignación',11,'add_solicitudreasignacion'),(42,'Can change Solicitud de Reasignación',11,'change_solicitudreasignacion'),(43,'Can delete Solicitud de Reasignación',11,'delete_solicitudreasignacion'),(44,'Can view Solicitud de Reasignación',11,'view_solicitudreasignacion'),(45,'Can add Perfil de Usuario',12,'add_perfilusuario'),(46,'Can change Perfil de Usuario',12,'change_perfilusuario'),(47,'Can delete Perfil de Usuario',12,'delete_perfilusuario'),(48,'Can view Perfil de Usuario',12,'view_perfilusuario');
/*!40000 ALTER TABLE `auth_permission` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `auth_user`
--

DROP TABLE IF EXISTS `auth_user`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `auth_user` (
  `id` int NOT NULL AUTO_INCREMENT,
  `password` varchar(128) NOT NULL,
  `last_login` datetime(6) DEFAULT NULL,
  `is_superuser` tinyint(1) NOT NULL,
  `username` varchar(150) NOT NULL,
  `first_name` varchar(150) NOT NULL,
  `last_name` varchar(150) NOT NULL,
  `email` varchar(254) NOT NULL,
  `is_staff` tinyint(1) NOT NULL,
  `is_active` tinyint(1) NOT NULL,
  `date_joined` datetime(6) NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `username` (`username`)
) ENGINE=InnoDB AUTO_INCREMENT=7 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `auth_user`
--

LOCK TABLES `auth_user` WRITE;
/*!40000 ALTER TABLE `auth_user` DISABLE KEYS */;
INSERT INTO `auth_user` VALUES (6,'pbkdf2_sha256$1000000$JwiC69HNN0iR75fxRbrVPo$vD1zaX4IgyKUdXLYpqURrXrIM1C1t1FfzTo0BZt3h4w=','2026-08-12 14:50:36.693281',0,'18807761-7','Felipe','Chamorro','felipechamorroretamal@gmail.com',0,1,'2026-08-12 14:50:35.876774');
/*!40000 ALTER TABLE `auth_user` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `auth_user_groups`
--

DROP TABLE IF EXISTS `auth_user_groups`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `auth_user_groups` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `user_id` int NOT NULL,
  `group_id` int NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `auth_user_groups_user_id_group_id_94350c0c_uniq` (`user_id`,`group_id`),
  KEY `auth_user_groups_group_id_97559544_fk_auth_group_id` (`group_id`),
  CONSTRAINT `auth_user_groups_group_id_97559544_fk_auth_group_id` FOREIGN KEY (`group_id`) REFERENCES `auth_group` (`id`),
  CONSTRAINT `auth_user_groups_user_id_6a12ed8b_fk_auth_user_id` FOREIGN KEY (`user_id`) REFERENCES `auth_user` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `auth_user_groups`
--

LOCK TABLES `auth_user_groups` WRITE;
/*!40000 ALTER TABLE `auth_user_groups` DISABLE KEYS */;
/*!40000 ALTER TABLE `auth_user_groups` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `auth_user_user_permissions`
--

DROP TABLE IF EXISTS `auth_user_user_permissions`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `auth_user_user_permissions` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `user_id` int NOT NULL,
  `permission_id` int NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `auth_user_user_permissions_user_id_permission_id_14a6b632_uniq` (`user_id`,`permission_id`),
  KEY `auth_user_user_permi_permission_id_1fbb5f2c_fk_auth_perm` (`permission_id`),
  CONSTRAINT `auth_user_user_permi_permission_id_1fbb5f2c_fk_auth_perm` FOREIGN KEY (`permission_id`) REFERENCES `auth_permission` (`id`),
  CONSTRAINT `auth_user_user_permissions_user_id_a95ead1b_fk_auth_user_id` FOREIGN KEY (`user_id`) REFERENCES `auth_user` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `auth_user_user_permissions`
--

LOCK TABLES `auth_user_user_permissions` WRITE;
/*!40000 ALTER TABLE `auth_user_user_permissions` DISABLE KEYS */;
/*!40000 ALTER TABLE `auth_user_user_permissions` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `core_cambiocuadrilla`
--

DROP TABLE IF EXISTS `core_cambiocuadrilla`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `core_cambiocuadrilla` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `accion` varchar(20) NOT NULL,
  `descripcion` longtext NOT NULL,
  `fecha` datetime(6) NOT NULL,
  `cuadrilla_id` bigint DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `core_cambiocuadrilla_cuadrilla_id_1df4de45_fk_core_cuadrilla_id` (`cuadrilla_id`),
  CONSTRAINT `core_cambiocuadrilla_cuadrilla_id_1df4de45_fk_core_cuadrilla_id` FOREIGN KEY (`cuadrilla_id`) REFERENCES `core_cuadrilla` (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=30 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `core_cambiocuadrilla`
--

LOCK TABLES `core_cambiocuadrilla` WRITE;
/*!40000 ALTER TABLE `core_cambiocuadrilla` DISABLE KEYS */;
/*!40000 ALTER TABLE `core_cambiocuadrilla` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `core_cuadrilla`
--

DROP TABLE IF EXISTS `core_cuadrilla`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `core_cuadrilla` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `nombre` varchar(100) NOT NULL,
  `estado` varchar(10) NOT NULL,
  `proyecto_id` int NOT NULL,
  `trabajador_id` bigint DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `unique_cuadrilla_nombre` (`nombre`),
  KEY `core_cuadrilla_proyecto_id_f91c52ca_fk_core_proyecto_codigo` (`proyecto_id`),
  KEY `core_cuadrilla_trabajador_id_68e7778b_fk_core_integrante_id` (`trabajador_id`),
  CONSTRAINT `core_cuadrilla_proyecto_id_f91c52ca_fk_core_proyecto_codigo` FOREIGN KEY (`proyecto_id`) REFERENCES `core_proyecto` (`codigo`),
  CONSTRAINT `core_cuadrilla_trabajador_id_68e7778b_fk_core_integrante_id` FOREIGN KEY (`trabajador_id`) REFERENCES `core_integrante` (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=28 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `core_cuadrilla`
--

LOCK TABLES `core_cuadrilla` WRITE;
/*!40000 ALTER TABLE `core_cuadrilla` DISABLE KEYS */;
/*!40000 ALTER TABLE `core_cuadrilla` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `core_integrante`
--

DROP TABLE IF EXISTS `core_integrante`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `core_integrante` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `cargo` varchar(20) NOT NULL,
  `cuadrilla_id` bigint DEFAULT NULL,
  `estado` varchar(15) NOT NULL,
  `fecha_actualizacion` datetime(6) NOT NULL,
  `notas` longtext NOT NULL,
  `usuario_id` int DEFAULT NULL,
  `apellido_trabajador` varchar(100) NOT NULL,
  `nombre_trabajador` varchar(100) NOT NULL,
  `licencia_fin` date DEFAULT NULL,
  `licencia_inicio` date DEFAULT NULL,
  `especialidad` varchar(20) DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `usuario_id` (`usuario_id`),
  KEY `core_integrante_cuadrilla_id_059cee3f_fk_core_cuadrilla_id` (`cuadrilla_id`),
  CONSTRAINT `core_integrante_cuadrilla_id_059cee3f_fk_core_cuadrilla_id` FOREIGN KEY (`cuadrilla_id`) REFERENCES `core_cuadrilla` (`id`),
  CONSTRAINT `core_integrante_usuario_id_b5b93382_fk_auth_user_id` FOREIGN KEY (`usuario_id`) REFERENCES `auth_user` (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=25 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `core_integrante`
--

LOCK TABLES `core_integrante` WRITE;
/*!40000 ALTER TABLE `core_integrante` DISABLE KEYS */;
INSERT INTO `core_integrante` VALUES (24,'lider',NULL,'disponible','2026-08-12 14:50:36.688478','',6,'','',NULL,NULL,NULL);
/*!40000 ALTER TABLE `core_integrante` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `core_proyecto`
--

DROP TABLE IF EXISTS `core_proyecto`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `core_proyecto` (
  `codigo` int NOT NULL AUTO_INCREMENT,
  `nombre` varchar(100) NOT NULL,
  `cliente` varchar(100) NOT NULL,
  `estado` varchar(20) NOT NULL,
  `fecha_inicio` date NOT NULL,
  `fecha_termino` date DEFAULT NULL,
  `presupuesto` decimal(12,2) NOT NULL,
  `direccion` varchar(255) NOT NULL,
  `ciudad` varchar(100) NOT NULL,
  `descripcion` longtext NOT NULL,
  PRIMARY KEY (`codigo`),
  UNIQUE KEY `core_proyecto_nombre_a0fa93b8_uniq` (`nombre`),
  UNIQUE KEY `unique_proyecto_nombre` (`nombre`)
) ENGINE=InnoDB AUTO_INCREMENT=19 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `core_proyecto`
--

LOCK TABLES `core_proyecto` WRITE;
/*!40000 ALTER TABLE `core_proyecto` DISABLE KEYS */;
/*!40000 ALTER TABLE `core_proyecto` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `core_solicitudreasignacion`
--

DROP TABLE IF EXISTS `core_solicitudreasignacion`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `core_solicitudreasignacion` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `estado` varchar(20) NOT NULL,
  `motivo` longtext NOT NULL,
  `fecha_solicitud` datetime(6) NOT NULL,
  `fecha_respuesta` datetime(6) DEFAULT NULL,
  `cuadrilla_destino_id` bigint NOT NULL,
  `cuadrilla_origen_id` bigint NOT NULL,
  `respondido_por_id` int DEFAULT NULL,
  `trabajador_id` bigint NOT NULL,
  PRIMARY KEY (`id`),
  KEY `core_solicitudreasig_cuadrilla_destino_id_09dc3400_fk_core_cuad` (`cuadrilla_destino_id`),
  KEY `core_solicitudreasig_cuadrilla_origen_id_5af0feb2_fk_core_cuad` (`cuadrilla_origen_id`),
  KEY `core_solicitudreasig_respondido_por_id_1931c308_fk_auth_user` (`respondido_por_id`),
  KEY `core_solicitudreasig_trabajador_id_40f09f33_fk_core_inte` (`trabajador_id`),
  CONSTRAINT `core_solicitudreasig_cuadrilla_destino_id_09dc3400_fk_core_cuad` FOREIGN KEY (`cuadrilla_destino_id`) REFERENCES `core_cuadrilla` (`id`),
  CONSTRAINT `core_solicitudreasig_cuadrilla_origen_id_5af0feb2_fk_core_cuad` FOREIGN KEY (`cuadrilla_origen_id`) REFERENCES `core_cuadrilla` (`id`),
  CONSTRAINT `core_solicitudreasig_respondido_por_id_1931c308_fk_auth_user` FOREIGN KEY (`respondido_por_id`) REFERENCES `auth_user` (`id`),
  CONSTRAINT `core_solicitudreasig_trabajador_id_40f09f33_fk_core_inte` FOREIGN KEY (`trabajador_id`) REFERENCES `core_integrante` (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=10 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `core_solicitudreasignacion`
--

LOCK TABLES `core_solicitudreasignacion` WRITE;
/*!40000 ALTER TABLE `core_solicitudreasignacion` DISABLE KEYS */;
/*!40000 ALTER TABLE `core_solicitudreasignacion` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `django_admin_log`
--

DROP TABLE IF EXISTS `django_admin_log`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `django_admin_log` (
  `id` int NOT NULL AUTO_INCREMENT,
  `action_time` datetime(6) NOT NULL,
  `object_id` longtext,
  `object_repr` varchar(200) NOT NULL,
  `action_flag` smallint unsigned NOT NULL,
  `change_message` longtext NOT NULL,
  `content_type_id` int DEFAULT NULL,
  `user_id` int NOT NULL,
  PRIMARY KEY (`id`),
  KEY `django_admin_log_content_type_id_c4bce8eb_fk_django_co` (`content_type_id`),
  KEY `django_admin_log_user_id_c564eba6_fk_auth_user_id` (`user_id`),
  CONSTRAINT `django_admin_log_content_type_id_c4bce8eb_fk_django_co` FOREIGN KEY (`content_type_id`) REFERENCES `django_content_type` (`id`),
  CONSTRAINT `django_admin_log_user_id_c564eba6_fk_auth_user_id` FOREIGN KEY (`user_id`) REFERENCES `auth_user` (`id`),
  CONSTRAINT `django_admin_log_chk_1` CHECK ((`action_flag` >= 0))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `django_admin_log`
--

LOCK TABLES `django_admin_log` WRITE;
/*!40000 ALTER TABLE `django_admin_log` DISABLE KEYS */;
/*!40000 ALTER TABLE `django_admin_log` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `django_content_type`
--

DROP TABLE IF EXISTS `django_content_type`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `django_content_type` (
  `id` int NOT NULL AUTO_INCREMENT,
  `app_label` varchar(100) NOT NULL,
  `model` varchar(100) NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `django_content_type_app_label_model_76bd3d3b_uniq` (`app_label`,`model`)
) ENGINE=InnoDB AUTO_INCREMENT=13 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `django_content_type`
--

LOCK TABLES `django_content_type` WRITE;
/*!40000 ALTER TABLE `django_content_type` DISABLE KEYS */;
INSERT INTO `django_content_type` VALUES (1,'admin','logentry'),(3,'auth','group'),(2,'auth','permission'),(4,'auth','user'),(5,'contenttypes','contenttype'),(10,'core','cambiocuadrilla'),(7,'core','cuadrilla'),(9,'core','integrante'),(8,'core','proyecto'),(11,'core','solicitudreasignacion'),(6,'sessions','session'),(12,'usuarios','perfilusuario');
/*!40000 ALTER TABLE `django_content_type` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `django_migrations`
--

DROP TABLE IF EXISTS `django_migrations`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `django_migrations` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `app` varchar(255) NOT NULL,
  `name` varchar(255) NOT NULL,
  `applied` datetime(6) NOT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=39 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `django_migrations`
--

LOCK TABLES `django_migrations` WRITE;
/*!40000 ALTER TABLE `django_migrations` DISABLE KEYS */;
INSERT INTO `django_migrations` VALUES (1,'contenttypes','0001_initial','2026-08-12 14:48:30.178360'),(2,'auth','0001_initial','2026-08-12 14:48:30.667430'),(3,'admin','0001_initial','2026-08-12 14:48:30.772156'),(4,'admin','0002_logentry_remove_auto_add','2026-08-12 14:48:30.778127'),(5,'admin','0003_logentry_add_action_flag_choices','2026-08-12 14:48:30.783579'),(6,'contenttypes','0002_remove_content_type_name','2026-08-12 14:48:30.867762'),(7,'auth','0002_alter_permission_name_max_length','2026-08-12 14:48:30.922367'),(8,'auth','0003_alter_user_email_max_length','2026-08-12 14:48:30.943050'),(9,'auth','0004_alter_user_username_opts','2026-08-12 14:48:30.949700'),(10,'auth','0005_alter_user_last_login_null','2026-08-12 14:48:30.999323'),(11,'auth','0006_require_contenttypes_0002','2026-08-12 14:48:31.001324'),(12,'auth','0007_alter_validators_add_error_messages','2026-08-12 14:48:31.007045'),(13,'auth','0008_alter_user_username_max_length','2026-08-12 14:48:31.059804'),(14,'auth','0009_alter_user_last_name_max_length','2026-08-12 14:48:31.117645'),(15,'auth','0010_alter_group_name_max_length','2026-08-12 14:48:31.133724'),(16,'auth','0011_update_proxy_permissions','2026-08-12 14:48:31.139751'),(17,'auth','0012_alter_user_first_name_max_length','2026-08-12 14:48:31.189577'),(18,'core','0001_initial','2026-08-12 14:48:31.324529'),(19,'core','0002_alter_cuadrilla_options_alter_integrante_options_and_more','2026-08-12 14:48:31.351033'),(20,'core','0003_alter_proyecto_presupuesto','2026-08-12 14:48:31.355974'),(21,'core','0004_alter_cuadrilla_proyecto','2026-08-12 14:48:31.360837'),(22,'core','0005_alter_integrante_cuadrilla','2026-08-12 14:48:31.474768'),(23,'core','0006_remove_integrante_cuadrilla','2026-08-12 14:48:31.510417'),(24,'core','0007_cuadrilla_integrantes_alter_cuadrilla_proyecto','2026-08-12 14:48:31.659466'),(25,'core','0008_remove_cuadrilla_integrantes_integrante_cuadrilla','2026-08-12 14:48:31.725641'),(26,'core','0009_integrante_estado_integrante_fecha_actualizacion_and_more','2026-08-12 14:48:31.944951'),(27,'core','0010_delete_all_integrantes_and_add_user','2026-08-12 14:48:32.046244'),(28,'core','0011_make_integrante_usuario_required','2026-08-12 14:48:32.153798'),(29,'core','0012_alter_integrante_options','2026-08-12 14:48:32.162897'),(30,'core','0013_alter_integrante_options_cuadrilla_trabajador_and_more','2026-08-12 14:48:32.735144'),(31,'core','0014_integrante_licencia_fin_integrante_licencia_inicio','2026-08-12 14:48:32.848332'),(32,'core','0015_integrante_especialidad_alter_proyecto_nombre_and_more','2026-08-12 14:48:32.967971'),(33,'core','0016_historialcuadrilla','2026-08-12 14:48:33.039187'),(34,'core','0017_alter_cambiocuadrilla_accion_and_more','2026-08-12 14:48:33.059709'),(35,'core','0018_alter_cambiocuadrilla_cuadrilla','2026-08-12 14:48:33.166829'),(36,'sessions','0001_initial','2026-08-12 14:48:33.202527'),(37,'usuarios','0001_initial','2026-08-12 14:48:33.286208'),(38,'usuarios','0002_perfilusuario_estado','2026-08-12 14:48:33.345355');
/*!40000 ALTER TABLE `django_migrations` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `django_session`
--

DROP TABLE IF EXISTS `django_session`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `django_session` (
  `session_key` varchar(40) NOT NULL,
  `session_data` longtext NOT NULL,
  `expire_date` datetime(6) NOT NULL,
  PRIMARY KEY (`session_key`),
  KEY `django_session_expire_date_a5c62663` (`expire_date`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `django_session`
--

LOCK TABLES `django_session` WRITE;
/*!40000 ALTER TABLE `django_session` DISABLE KEYS */;
INSERT INTO `django_session` VALUES ('yw4c86vca7ac463219lmbskpunk3k1u4','.eJxVjssKwjAQRf8lawl5NBni0r3fUDIzia1KC027EPHfTaSCboZh7pnDfYo-buvQbyUt_cjiKLw4_N4w0i1NLeBrnC6zpHlalxFlQ-SeFnmeOd1PO_snGGIZ6rd2HRGCzkCowRnoGDNmsimABQU2W7TBGEOewdnoNIOGzlt2FFJurT66kmhbxvXx9QZSBkF58p7rrnLjMegqTrFO8XoDI3BJUw:1wuAHs:B-3nEIZLosr1FRlfgpjQn0UaXo-mMcpqztL20FmmdzI','2026-08-26 14:50:36.757827');
/*!40000 ALTER TABLE `django_session` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `usuarios_perfilusuario`
--

DROP TABLE IF EXISTS `usuarios_perfilusuario`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `usuarios_perfilusuario` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `rol` varchar(20) NOT NULL,
  `fecha_registro` datetime(6) NOT NULL,
  `fecha_actualizacion` datetime(6) NOT NULL,
  `usuario_id` int NOT NULL,
  `estado` varchar(15) NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `usuario_id` (`usuario_id`),
  CONSTRAINT `usuarios_perfilusuario_usuario_id_70ec3749_fk_auth_user_id` FOREIGN KEY (`usuario_id`) REFERENCES `auth_user` (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=7 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `usuarios_perfilusuario`
--

LOCK TABLES `usuarios_perfilusuario` WRITE;
/*!40000 ALTER TABLE `usuarios_perfilusuario` DISABLE KEYS */;
INSERT INTO `usuarios_perfilusuario` VALUES (6,'lider_cuadrilla','2026-08-12 14:50:36.681672','2026-08-12 14:50:36.685222',6,'activo');
/*!40000 ALTER TABLE `usuarios_perfilusuario` ENABLE KEYS */;
UNLOCK TABLES;
/*!40103 SET TIME_ZONE=@OLD_TIME_ZONE */;

/*!40101 SET SQL_MODE=@OLD_SQL_MODE */;
/*!40014 SET FOREIGN_KEY_CHECKS=@OLD_FOREIGN_KEY_CHECKS */;
/*!40014 SET UNIQUE_CHECKS=@OLD_UNIQUE_CHECKS */;
/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
/*!40111 SET SQL_NOTES=@OLD_SQL_NOTES */;

-- Dump completed on 2026-10-08 12:50:22
