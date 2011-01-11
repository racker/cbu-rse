CREATE DATABASE IF NOT EXISTS `rse`
  CHARACTER SET = utf8;
  
USE rse;
  
CREATE TABLE IF NOT EXISTS `Events` (
  `id` bigint(20) unsigned NOT NULL AUTO_INCREMENT,
  `data` mediumtext COMMENT 'Max size is 16 MB',
  `channel` varchar(255) NOT NULL,
  `user_agent` varchar(255) NOT NULL,
  `user_agent_uuid` char(36) NOT NULL,
  `created_at` datetime NOT NULL COMMENT 'UTC',
  PRIMARY KEY (`id`) USING BTREE,
  KEY `id_channel_uuid_idx` (`id`,`channel`,`user_agent_uuid`)
) ENGINE=MyISAM DEFAULT CHARSET=utf8;

------------------------------
-- Be sure to add the following to my.cnf
-- event_scheduler=ON
------------------------------
DROP EVENT IF EXISTS `evt_GarbageCollection`;
CREATE EVENT `evt_GarbageCollection` ON SCHEDULE EVERY 1 MINUTE STARTS '2010-11-08 14:57:32' ON COMPLETION NOT PRESERVE ENABLE DO DELETE FROM Events WHERE Events.created_at < DATE_SUB(UTC_TIMESTAMP(), INTERVAL 2 MINUTE);

create user 'rse'@'%' identified by 'insert-password-here';

-- Only for slave
grant select, execute on rse.* to 'rse'@'%';

-- Only for master
grant insert on rse.* to 'rse'@'%';
create user 'servant'@'%' identified by  'insert-password-here';
grant REPLICATION SLAVE ON *.* to 'servant'@'%';


