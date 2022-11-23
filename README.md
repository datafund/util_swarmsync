# Python util for uploading files to swarm

creates folder in home named .swarmsync where it stores lists
 
## features
 - saves references
 - optional tagging of upload
 - keeps upload list in todo, so you can resume or retry failed or canceled uploads.
 - support concurrent uploads (to the same endpoint)
 - can check stewardship of uploaded references
 - supports concurrent uploads

todo: 
 - merge stewardship responses into responses list
 - improve readme
 - add support for simultaneous uploads to multiple bees
 - add support for private files/single owner chunks
 - add mac build
